import logging
from typing import Any

from app.pipeline.comparacion_cursos.aplicar_accion import aplicar_accion
from app.pipeline.comparacion_cursos.constructor_indice import (
    construir_indice_claves_base,
    construir_indice_nucleo,
    construir_indice_shortnames,
)
from app.pipeline.comparacion_cursos.desaparecidos import encontrar_cursos_desaparecidos
from app.pipeline.comparacion_cursos.manejador_acciones import (
    manejar_docente_diferente,
    manejar_mismo_docente,
    manejar_mismo_nucleo_grupo_diferente,
)
from app.pipeline.comparacion_cursos.umbrales import (
    EDAD_MAXIMA_CURSO_SEGUNDOS,
)
from app.pipeline.comparacion_cursos.utilidades import (
    construir_clave_base,
    construir_mapa_matriculaciones,
    es_curso_oculto,
    obtener_profesor_curso,
    obtener_sufijo,
    primer_visible,
)
from app.pipeline.nombres_cortos import SIAUGESMAT_PATTERN, parsear_shortname

logger = logging.getLogger(__name__)


def _norm_email(value: str) -> str:
    return (value or "").strip().lower()


def _misma_persona_por_correo(
    username_a: str | None,
    username_b: str | None,
    username_emails: dict[str, str] | None,
) -> bool:
    """Determina si dos usernames corresponden a la misma persona por email.

    El comparador trabaja con usernames (ETL o resueltos), pero el ETL puede
    diferir del username real de Moodle para la misma persona (p. ej. un email
    ya asociado a otro username). Cuando los usernames difieren, se resuelve
    cada uno a su email (si el mapa los conoce) y se comparan emails.
    """
    if not username_a or not username_b or not username_emails:
        return False
    email_a = _norm_email(username_emails.get(username_a, ""))
    email_b = _norm_email(username_emails.get(username_b, ""))
    return bool(email_a and email_b and email_a == email_b)


class ServicioComparacionCursos:
    @classmethod
    async def comparar(
        cls,
        existing_courses: list[dict],
        new_courses: list[dict],
        new_enrolments: list[dict],
        re_upload: bool = False,
        courses_with_teacher: dict[str, str] = None,
        *,
        username_emails: dict[str, str] = None,
        max_age_seconds: int = EDAD_MAXIMA_CURSO_SEGUNDOS,
    ) -> dict[str, Any]:
        if courses_with_teacher is None:
            courses_with_teacher = {}
        siaugesmat_courses = [
            c for c in existing_courses if SIAUGESMAT_PATTERN.match(c.get("shortname", ""))
        ]

        existing_by_shortname = construir_indice_shortnames(siaugesmat_courses)
        existing_by_base_key = construir_indice_claves_base(siaugesmat_courses)
        existing_by_core = construir_indice_nucleo(siaugesmat_courses)

        enrolment_index = construir_mapa_matriculaciones(new_enrolments)

        to_create: list[dict] = []
        to_delete: list[str] = []
        to_activate: list[str] = []
        to_hide: list[str] = []
        to_update: list[dict] = []
        alerts: list[dict] = []
        logs: list[dict] = []

        new_shortnames = set()
        new_base_keys = set()

        new_groups_by_core: dict[tuple[str, ...], set] = {}
        new_program_codes: set[str] = set()
        for course in new_courses:
            parsed = parsear_shortname(course["shortname"])
            if parsed:
                core_key = (parsed["cod_prog"], parsed["cod_curso"], parsed["semestre"])
                new_groups_by_core.setdefault(core_key, set()).add(parsed["grupo"])
                new_program_codes.add(parsed["cod_prog"])

        for course in new_courses:
            sn = course["shortname"]
            new_shortnames.add(sn)
            parsed_new = parsear_shortname(sn)
            professor = enrolment_index.get(sn, "")
            new_suffix = parsed_new.get("suffix", "") if parsed_new else ""

            if sn in existing_by_shortname:
                existing = existing_by_shortname[sn]
                existing_prof = obtener_profesor_curso(existing)

                if sn not in courses_with_teacher:
                    action, detail = (
                        "recreate",
                        {
                            "reason": "orphan_course",
                            "old_shortname": existing.get("shortname", sn),
                            "professor": professor,
                            "old_professor": existing_prof or "",
                        },
                    )
                elif (existing_prof and existing_prof == professor) or courses_with_teacher.get(
                    sn
                ) == professor:
                    action, detail = manejar_mismo_docente(
                        existing,
                        sn,
                        professor,
                        max_age_seconds=max_age_seconds,
                    )
                elif _misma_persona_por_correo(
                    courses_with_teacher.get(sn) or existing_prof,
                    professor,
                    username_emails,
                ):
                    logger.info(
                        f"Curso {sn}: profesor ETL '{professor}' coincide por email "
                        f"con el profesor de Moodle '{courses_with_teacher.get(sn)}'; "
                        "se trata como mismo profesor"
                    )
                    action, detail = manejar_mismo_docente(
                        existing,
                        sn,
                        professor,
                        max_age_seconds=max_age_seconds,
                    )
                else:
                    action, detail = manejar_docente_diferente(
                        existing,
                        sn,
                        professor,
                        existing_prof,
                        should_hide_existing=True,
                        re_upload=re_upload,
                        max_age_seconds=max_age_seconds,
                    )

            elif parsed_new:
                base_key = construir_clave_base(parsed_new)
                new_base_keys.add(base_key)
                candidates = existing_by_base_key.get(base_key, [])

                if candidates:
                    match = next(
                        (
                            c
                            for c in candidates
                            if obtener_sufijo(c.get("shortname", "")) == new_suffix
                        ),
                        None,
                    )
                    if match:
                        existing_prof = obtener_profesor_curso(match)
                        if existing_prof and existing_prof == professor:
                            action, detail = manejar_mismo_docente(
                                match,
                                sn,
                                professor,
                                max_age_seconds=max_age_seconds,
                            )
                        else:
                            action, detail = manejar_docente_diferente(
                                match,
                                sn,
                                professor,
                                existing_prof,
                                re_upload=re_upload,
                                max_age_seconds=max_age_seconds,
                            )
                    elif new_suffix:
                        match = next(
                            (
                                c
                                for c in candidates
                                if obtener_profesor_curso(c) == professor
                                or (
                                    c.get("shortname", "") in courses_with_teacher
                                    and courses_with_teacher[c.get("shortname", "")] == professor
                                )
                            ),
                            None,
                        )
                        if match:
                            old_hidden = es_curso_oculto(match)
                            action, detail = (
                                "rename_group",
                                {
                                    "reason": "suffix_update",
                                    "professor": professor,
                                    "old_shortname": match["shortname"],
                                    "old_suffix": obtener_sufijo(match["shortname"]),
                                    "new_suffix": new_suffix,
                                    "reactivate": old_hidden,
                                },
                            )
                        else:
                            target = primer_visible(candidates)
                            existing_prof = obtener_profesor_curso(target)
                            action, detail = manejar_docente_diferente(
                                target,
                                sn,
                                professor,
                                existing_prof,
                                should_hide_existing=True,
                                re_upload=re_upload,
                                max_age_seconds=max_age_seconds,
                            )
                    else:
                        target = primer_visible(candidates)
                        existing_prof = obtener_profesor_curso(target)
                        action, detail = manejar_docente_diferente(
                            target,
                            sn,
                            professor,
                            existing_prof,
                            should_hide_existing=True,
                            re_upload=re_upload,
                            max_age_seconds=max_age_seconds,
                        )
                else:
                    core_key = (
                        parsed_new["cod_prog"],
                        parsed_new["cod_curso"],
                        parsed_new["semestre"],
                    )
                    same_core_courses = existing_by_core.get(core_key, [])

                    if same_core_courses:
                        action, detail = manejar_mismo_nucleo_grupo_diferente(
                            same_core_courses, parsed_new, sn, professor, new_groups_by_core
                        )
                    else:
                        action, detail = "create", {"reason": "new", "professor": professor}
            else:
                action, detail = "create", {"reason": "new", "professor": professor}

            aplicar_accion(
                action,
                detail,
                sn,
                professor,
                parsed_new,
                to_create,
                to_delete,
                to_activate,
                to_hide,
                to_update,
                alerts,
                logs,
            )

        encontrar_cursos_desaparecidos(
            existing_by_shortname,
            existing_by_base_key,
            new_shortnames,
            new_base_keys,
            new_program_codes,
            to_delete,
            to_hide,
            alerts,
            logs,
            max_age_seconds=max_age_seconds,
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
