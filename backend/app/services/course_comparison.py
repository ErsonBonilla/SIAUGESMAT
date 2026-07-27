"""
Servicio de comparación de cursos (FASE 2 del Módulo de Novedades).

Compara los cursos de la nueva carga académica contra los cursos
existentes en Moodle que coinciden con el patrón SIAUGESMAT,
y determina las acciones a realizar.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.parsers.patterns import SIAUGESMAT_PATTERN, parse_shortname

logger = logging.getLogger(__name__)

# Umbrales
EIGHTEEN_MONTHS_SECONDS = 18 * 30 * 24 * 3600
SIX_MONTHS_SECONDS = 6 * 30 * 24 * 3600


class CourseComparisonService:

    @classmethod
    async def compare(
        cls,
        existing_courses: List[Dict],
        new_courses: List[Dict],
        new_enrolments: List[Dict],
        re_upload: bool = False,
        courses_with_teacher: Set[str] = None,
    ) -> Dict[str, Any]:
        """
        Compara los cursos de la nueva carga contra los existentes en Moodle.

        Args:
            existing_courses: Lista de cursos existentes en Moodle (ya filtrados
                              por SIAUGESMAT_PATTERN).
            re_upload: True si es una re-carga del mismo semestre.
                       En ese caso, los cambios de profesor siempre hacen
                       recreate (sin ocultar), asumiendo renuncia/despido.
            courses_with_teacher: Set de shortnames de cursos que tienen
                                  editingteacher en Moodle.

        Returns:
            Diccionario con:
                - to_create: cursos a crear
                - to_delete: shortnames de cursos a eliminar
                - to_activate: shortnames de cursos ocultos a activar
                - to_hide: shortnames de cursos a ocultar
                - to_update: cursos a renombrar (grupo cambiado)
                - alerts: alertas que requieren revisión manual
                - logs: registros detallados de cada acción/incidencia
        """
        if courses_with_teacher is None:
            courses_with_teacher = set()
        siaugesmat_courses = [
            c for c in existing_courses
            if SIAUGESMAT_PATTERN.match(c.get("shortname", ""))
        ]

        existing_by_shortname = cls._build_shortname_index(siaugesmat_courses)
        existing_by_base_key = cls._build_base_key_index(siaugesmat_courses)
        existing_by_core = cls._build_core_index(siaugesmat_courses)

        enrolment_index: Dict[str, str] = {}
        for enr in new_enrolments:
            enrolment_index[enr["course_shortname"]] = enr["username"]

        to_create: List[Dict] = []
        to_delete: List[str] = []
        to_activate: List[str] = []
        to_hide: List[str] = []
        to_update: List[Dict] = []
        alerts: List[Dict] = []
        logs: List[Dict] = []

        new_shortnames = set()
        new_base_keys = set()

        # Índice de grupos presentes en la nueva carga (por core key)
        new_groups_by_core: Dict[Tuple[str, ...], set] = {}
        new_program_codes: Set[str] = set()
        for course in new_courses:
            parsed = cls._parse_shortname(course["shortname"])
            if parsed:
                core_key = (parsed["cod_prog"], parsed["cod_curso"], parsed["semestre"])
                new_groups_by_core.setdefault(core_key, set()).add(parsed["grupo"])
                new_program_codes.add(parsed["cod_prog"])

        for course in new_courses:
            sn = course["shortname"]
            new_shortnames.add(sn)
            parsed_new = cls._parse_shortname(sn)
            professor = enrolment_index.get(sn, "")
            new_suffix = parsed_new.get("suffix", "") if parsed_new else ""

            # ---- Matching exacto por shortname ----
            if sn in existing_by_shortname:
                existing = existing_by_shortname[sn]
                existing_prof = cls._get_course_professor(existing)

                if sn not in courses_with_teacher:
                    action, detail = "recreate", {
                        "reason": "orphan_course",
                        "old_shortname": existing.get("shortname", sn),
                        "professor": professor,
                        "old_professor": existing_prof or "",
                    }
                elif existing_prof and existing_prof == professor:
                    action, detail = cls._handle_same_professor(existing, sn, professor)
                else:
                    action, detail = cls._handle_different_professor(
                        existing, sn, professor, existing_prof,
                        should_hide_existing=True,
                        re_upload=re_upload,
                    )

            # ---- Matching por base key (mismos campos, distinta cédula) ----
            elif parsed_new:
                base_key = cls._build_base_key(parsed_new)
                new_base_keys.add(base_key)
                candidates = existing_by_base_key.get(base_key, [])

                if candidates:
                    # Buscar candidato con el MISMO sufijo
                    match = next(
                        (c for c in candidates
                         if cls._get_suffix(c.get("shortname", "")) == new_suffix),
                        None,
                    )
                    if match:
                        existing_prof = cls._get_course_professor(match)
                        if existing_prof and existing_prof == professor:
                            action, detail = cls._handle_same_professor(match, sn, professor)
                        else:
                            action, detail = cls._handle_different_professor(
                                match, sn, professor, existing_prof,
                                re_upload=re_upload,
                            )
                    elif new_suffix:
                        # No coincide sufijo → buscar por profesor (migración)
                        match = next(
                            (c for c in candidates
                             if cls._get_course_professor(c) == professor
                             or c.get("shortname", "") in courses_with_teacher),
                            None,
                        )
                        if match:
                            old_hidden = cls._is_course_hidden(match)
                            action, detail = "rename_group", {
                                "reason": "suffix_update",
                                "professor": professor,
                                "old_shortname": match["shortname"],
                                "old_suffix": cls._get_suffix(match["shortname"]),
                                "new_suffix": new_suffix,
                                "reactivate": old_hidden,
                            }
                        else:
                            # Profesor distinto → ocultar el candidato visible
                            target = cls._first_visible(candidates)
                            existing_prof = cls._get_course_professor(target)
                            action, detail = cls._handle_different_professor(
                                target, sn, professor, existing_prof,
                                should_hide_existing=True,
                                re_upload=re_upload,
                            )
                    else:
                        # Sin sufijo → ocultar el candidato visible
                        target = cls._first_visible(candidates)
                        existing_prof = cls._get_course_professor(target)
                        action, detail = cls._handle_different_professor(
                            target, sn, professor, existing_prof,
                            should_hide_existing=True,
                            re_upload=re_upload,
                        )
                else:
                    # ---- Matching por core (mismo cod_prog+cod_curso+semestre, distinto grupo) ----
                    core_key = (
                        parsed_new["cod_prog"],
                        parsed_new["cod_curso"],
                        parsed_new["semestre"],
                    )
                    same_core_courses = existing_by_core.get(core_key, [])

                    if same_core_courses:
                        action, detail = cls._handle_same_core_different_group(
                            same_core_courses, parsed_new, sn, professor, new_groups_by_core
                        )
                    else:
                        action, detail = "create", {"reason": "new", "professor": professor}
            else:
                action, detail = "create", {"reason": "new", "professor": professor}

            cls._apply_action(
                action, detail, sn, professor, parsed_new,
                to_create, to_delete, to_activate, to_hide, to_update, alerts, logs,
            )

        cls._find_disappeared_courses(
            existing_by_shortname, existing_by_base_key, new_shortnames, new_base_keys,
            new_program_codes, to_delete, to_hide, alerts, logs,
        )

        return {
            "to_create": to_create,
            "to_delete": to_delete,
            "to_activate": to_activate,
            "to_hide": to_hide,
            "to_update": to_update,
            "alerts": alerts,
            "logs": logs,
        }

    # ------------------------------------------------------------------
    # Helpers de parsing e indexación
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_shortname(shortname: str) -> Optional[Dict[str, str]]:
        return parse_shortname(shortname)

    @staticmethod
    def _build_base_key(parsed: Dict) -> Tuple[str, ...]:
        return (
            parsed["cat_prefix"],
            parsed["cod_prog"],
            parsed["semestre"],
            parsed["cod_curso"],
            parsed["grupo"],
        )

    @staticmethod
    def _build_shortname_index(courses: List[Dict]) -> Dict[str, Dict]:
        return {c.get("shortname", ""): c for c in courses if c.get("shortname")}

    @staticmethod
    def _build_base_key_index(courses: List[Dict]) -> Dict[Tuple[str, ...], List[Dict]]:
        index: Dict[Tuple[str, ...], List[Dict]] = {}
        for c in courses:
            sn = c.get("shortname", "")
            parsed = parse_shortname(sn)
            if parsed:
                key = (parsed["cat_prefix"], parsed["cod_prog"], parsed["semestre"],
                       parsed["cod_curso"], parsed["grupo"])
                index.setdefault(key, []).append(c)
        return index

    @staticmethod
    def _build_core_index(courses: List[Dict]) -> Dict[Tuple[str, ...], List[Dict]]:
        index: Dict[Tuple[str, ...], List[Dict]] = {}
        for c in courses:
            sn = c.get("shortname", "")
            parsed = parse_shortname(sn)
            if parsed:
                key = (parsed["cod_prog"], parsed["cod_curso"], parsed["semestre"])
                index.setdefault(key, []).append(c)
        return index

    @staticmethod
    def _get_suffix(shortname: str) -> str:
        parsed = parse_shortname(shortname)
        if not parsed:
            return ""
        return parsed["suffix"] or ""

    # ------------------------------------------------------------------
    # Metadatos de cursos en Moodle
    # ------------------------------------------------------------------

    @staticmethod
    def _get_course_professor(course: Dict) -> Optional[str]:
        custom = course.get("customfields", [])
        for field in custom:
            if field.get("shortname") == "professor":
                return field.get("value")
        return None

    @staticmethod
    def _get_course_age_seconds(course: Dict) -> int:
        created = course.get("timecreated", 0)
        if not created:
            created = course.get("startdate", 0)
        return int(datetime.now(timezone.utc).timestamp()) - created

    @staticmethod
    def _is_course_hidden(course: Dict) -> bool:
        return course.get("visible", 1) == 0

    @staticmethod
    def _first_visible(candidates: List[Dict]) -> Dict:
        """Retorna el primer candidato visible, o el primero si todos están ocultos."""
        for c in candidates:
            if c.get("visible", 1) == 1:
                return c
        return candidates[0]

    # ------------------------------------------------------------------
    # Manejadores de casos
    # ------------------------------------------------------------------

    @classmethod
    def _handle_same_professor(
        cls, existing: Dict, sn: str, professor: str
    ) -> Tuple[str, Dict]:
        age = cls._get_course_age_seconds(existing)
        existing_sn = existing.get("shortname", "")
        needs_rename = existing_sn != sn

        if age >= EIGHTEEN_MONTHS_SECONDS:
            return "recreate", {
                "reason": "old_course_cleanup",
                "professor": professor,
                "age_seconds": age,
            }

        if cls._is_course_hidden(existing):
            if needs_rename:
                return "rename_group", {
                    "reason": "same_professor_hidden_rename",
                    "professor": professor,
                    "old_shortname": existing_sn,
                    "new_shortname": sn,
                    "reactivate": True,
                }
            return "activate", {
                "reason": "same_professor_hidden",
                "professor": professor,
            }

        if needs_rename:
            return "rename_group", {
                "reason": "same_professor_cedula_update",
                "professor": professor,
                "old_shortname": existing_sn,
                "new_shortname": sn,
            }
        return "none", {"reason": "same_professor", "professor": professor}

    @classmethod
    def _handle_different_professor(
        cls,
        existing: Dict,
        sn: str,
        new_prof: str,
        old_prof: Optional[str],
        should_hide_existing: bool = False,
        re_upload: bool = False,
    ) -> Tuple[str, Dict]:
        """
        Decide qué acción tomar cuando el profesor cambia.

        Args:
            should_hide_existing: True si se debe ocultar el curso existente
                                   en lugar de eliminarlo (preserva el curso
                                   del profesor anterior).
            re_upload: True si es re-carga del mismo semestre.
                       En ese caso el profesor renunció/despidieron →
                       siempre recreate, sin ocultar.
        """
        age = cls._get_course_age_seconds(existing)
        detail = {
            "reason": "teacher_change",
            "old_shortname": existing.get("shortname", ""),
            "old_professor": old_prof or "",
            "new_professor": new_prof,
            "age_seconds": age,
        }

        if re_upload:
            # Re-carga mismo semestre → profesor renunció o fue despedido
            detail["reason"] = "teacher_change_re_upload"
            return "recreate", detail

        if age >= EIGHTEEN_MONTHS_SECONDS:
            # Curso muy antiguo: eliminar y crear de nuevo
            detail["reason"] = "teacher_change_old"
            return "recreate", detail
        else:
            # Curso reciente: ocultar y crear uno nuevo (preservar derechos de autor)
            detail["reason"] = "teacher_change_recent"
            if should_hide_existing:
                return "hide_and_create", detail
            return "recreate", detail

    @classmethod
    def _handle_same_core_different_group(
        cls,
        same_core_courses: List[Dict],
        parsed_new: Dict,
        sn: str,
        professor: str,
        new_groups_by_core: Dict[Tuple[str, ...], set],
    ) -> Tuple[str, Dict]:
        core_key = (parsed_new["cod_prog"], parsed_new["cod_curso"], parsed_new["semestre"])
        new_groups = new_groups_by_core.get(core_key, set())

        for existing in same_core_courses:
            existing_sn = existing.get("shortname", "")
            parsed_existing = parse_shortname(existing_sn)
            if not parsed_existing:
                continue
            existing_group = parsed_existing["grupo"]
            new_group = parsed_new["grupo"]

            if existing_group == new_group:
                continue

            existing_prof = cls._get_course_professor(existing)
            template = existing_sn

            if existing_prof and existing_prof == professor:
                if existing_group not in new_groups:
                    return "rename_group", {
                        "reason": "same_professor_group_changed",
                        "professor": professor,
                        "old_shortname": existing_sn,
                        "old_group": existing_group,
                        "new_group": new_group,
                    }
                return "create_with_template", {
                    "reason": "same_professor_new_group",
                    "professor": professor,
                    "group_origin": existing_group,
                    "group_new": new_group,
                    "template_shortname": template,
                }
            else:
                return "create", {
                    "reason": "different_professor_new_group",
                    "professor": professor,
                    "group_origin": existing_group,
                    "group_new": new_group,
                }

        return "create", {"reason": "new", "professor": professor}

    @classmethod
    def _find_disappeared_courses(
        cls,
        existing_by_shortname: Dict[str, Dict],
        existing_by_base_key: Dict[Tuple[str, ...], List[Dict]],
        new_shortnames: set,
        new_base_keys: set,
        new_program_codes: Set[str],
        to_delete: List[str],
        to_hide: List[str],
        alerts: List[Dict],
        logs: List[Dict],
    ):
        """
        Cursos que desaparecieron del Excel.

        - Solo se evalúan cursos cuyos programas están en el nuevo Excel.
          Esto evita eliminar cursos de programas no incluidos en la carga.
        - Si el curso comparte base key con algún nuevo: se considera reemplazado
          (manejado en compare), no se toca.
        """
        for sn, existing in existing_by_shortname.items():
            if sn in new_shortnames:
                continue

            parsed = parse_shortname(sn)
            if parsed:
                if parsed["cod_prog"] not in new_program_codes:
                    continue  # No tocar cursos de programas fuera del Excel
                base_key = cls._build_base_key(parsed)
                if base_key in new_base_keys:
                    continue  # Este curso comparte base key con uno nuevo

            age = cls._get_course_age_seconds(existing)
            if age >= SIX_MONTHS_SECONDS:
                to_delete.append(sn)
                alerts.append({
                    "shortname": sn,
                    "reason": "disappeared",
                    "age_seconds": age,
                })
                logs.append({
                    "phase": "2",
                    "action": "course_deleted",
                    "identifier": sn,
                    "detail": {"reason": "disappeared", "age_seconds": age},
                })
            else:
                to_hide.append(sn)
                alerts.append({
                    "shortname": sn,
                    "reason": "disappeared_recent",
                    "age_seconds": age,
                })
                logs.append({
                    "phase": "2",
                    "action": "course_disappeared_recent_hidden",
                    "identifier": sn,
                    "detail": {"reason": "disappeared_recent", "age_seconds": age},
                })

    @classmethod
    def _apply_action(
        cls,
        action: str,
        detail: Dict,
        sn: str,
        professor: str,
        parsed_new: Optional[Dict],
        to_create: List,
        to_delete: List,
        to_activate: List,
        to_hide: List,
        to_update: List,
        alerts: List,
        logs: List,
    ):
        phase = "2"
        if action == "create":
            to_create.append({"shortname": sn, "professor": professor})
            logs.append({
                "phase": phase, "action": "course_created",
                "identifier": sn, "detail": detail,
            })
        elif action == "create_with_template":
            to_create.append({
                "shortname": sn,
                "professor": professor,
                "template_shortname": detail.get("template_shortname"),
            })
            logs.append({
                "phase": phase, "action": "course_created_with_template",
                "identifier": sn, "detail": detail,
            })
        elif action == "recreate":
            old_sn = detail.get("old_shortname", sn)
            to_delete.append(old_sn)
            to_create.append({"shortname": sn, "professor": professor})
            logs.append({
                "phase": phase, "action": "course_recreated",
                "identifier": sn, "detail": detail,
            })
        elif action == "hide_and_create":
            old_sn = detail.get("old_shortname", sn)
            to_hide.append(old_sn)
            to_create.append({"shortname": sn, "professor": professor})
            alerts.append({
                "shortname": sn,
                "reason": "teacher_change_recent",
                "old_professor": detail.get("old_professor", ""),
                "new_professor": detail.get("new_professor", ""),
                "age_seconds": detail.get("age_seconds", 0),
            })
            logs.append({
                "phase": phase, "action": "course_hidden_and_created",
                "identifier": sn, "detail": detail,
            })
        elif action == "rename_group":
            entry = {
                "old_shortname": detail["old_shortname"],
                "shortname": sn,
                "professor": professor,
            }
            if detail.get("reactivate"):
                entry["reactivate"] = True
                to_activate.append(detail["old_shortname"])
            to_update.append(entry)
            logs.append({
                "phase": phase, "action": "course_renamed",
                "identifier": sn,
                "detail": {
                    **detail,
                    "new_shortname": sn,
                },
            })
        elif action == "activate":
            to_activate.append(sn)
            logs.append({
                "phase": phase, "action": "course_activated",
                "identifier": sn, "detail": detail,
            })
        elif action == "create_with_alert":
            to_create.append({"shortname": sn, "professor": professor})
            alerts.append({
                "shortname": sn,
                "reason": detail["reason"],
                "old_professor": detail.get("old_professor", ""),
                "new_professor": detail.get("new_professor", ""),
                "age_seconds": detail.get("age_seconds", 0),
            })
            logs.append({
                "phase": phase, "action": "alert_teacher_change_recent",
                "identifier": sn, "detail": detail,
            })
        elif action == "alert_orphan":
            alerts.append({
                "shortname": sn,
                "reason": "orphan_course",
                "old_professor": detail.get("old_professor", ""),
                "new_professor": detail.get("professor", ""),
            })
            logs.append({
                "phase": phase, "action": "alert_orphan_course",
                "identifier": sn, "detail": detail,
            })
        elif action == "none":
            logs.append({
                "phase": phase, "action": "course_unchanged",
                "identifier": sn, "detail": detail,
            })
