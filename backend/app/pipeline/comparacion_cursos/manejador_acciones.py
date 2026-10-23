from app.pipeline.comparacion_cursos.umbrales import EDAD_MAXIMA_CURSO_SEGUNDOS
from app.pipeline.comparacion_cursos.utilidades import (
    es_curso_oculto,
    obtener_edad_curso_segundos,
    obtener_profesor_curso,
)
from app.pipeline.nombres_cortos import parsear_shortname


def manejar_mismo_docente(
    existing: dict,
    sn: str,
    professor: str,
    *,
    max_age_seconds: int = EDAD_MAXIMA_CURSO_SEGUNDOS,
) -> tuple[str, dict]:
    age = obtener_edad_curso_segundos(existing)
    existing_sn = existing.get("shortname", "")
    needs_rename = existing_sn != sn

    if age >= max_age_seconds:
        return "recreate", {
            "reason": "old_course_cleanup",
            "professor": professor,
            "age_seconds": age,
        }

    if es_curso_oculto(existing):
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


def manejar_docente_diferente(
    existing: dict,
    sn: str,
    new_prof: str,
    old_prof: str | None,
    should_hide_existing: bool = False,
    re_upload: bool = False,
    *,
    max_age_seconds: int = EDAD_MAXIMA_CURSO_SEGUNDOS,
) -> tuple[str, dict]:
    age = obtener_edad_curso_segundos(existing)
    detail = {
        "reason": "teacher_change",
        "old_shortname": existing.get("shortname", ""),
        "old_professor": old_prof or "",
        "new_professor": new_prof,
        "age_seconds": age,
    }

    if re_upload:
        detail["reason"] = "teacher_change_re_upload"
        return "recreate", detail

    if age >= max_age_seconds:
        detail["reason"] = "teacher_change_old"
        return "recreate", detail
    detail["reason"] = "teacher_change_recent"
    if should_hide_existing:
        return "hide_and_create", detail
    return "recreate", detail


def manejar_mismo_nucleo_grupo_diferente(
    same_core_courses: list[dict],
    parsed_new: dict,
    sn: str,
    professor: str,
    new_groups_by_core: dict[tuple[str, ...], set],
) -> tuple[str, dict]:
    core_key = (parsed_new["cod_prog"], parsed_new["cod_curso"], parsed_new["semestre"])
    new_groups = new_groups_by_core.get(core_key, set())

    for existing in same_core_courses:
        existing_sn = existing.get("shortname", "")
        parsed_existing = parsear_shortname(existing_sn)
        if not parsed_existing:
            continue
        existing_group = parsed_existing["grupo"]
        new_group = parsed_new["grupo"]

        if existing_group == new_group:
            continue

        existing_prof = obtener_profesor_curso(existing)
        template = existing_sn

        if existing_prof and existing_prof == professor:
            if existing_group not in new_groups:
                entry = {
                    "reason": "same_professor_group_changed",
                    "professor": professor,
                    "old_shortname": existing_sn,
                    "old_group": existing_group,
                    "new_group": new_group,
                }
                if es_curso_oculto(existing):
                    entry["reactivate"] = True
                return "rename_group", entry
            return "create_with_template", {
                "reason": "same_professor_new_group",
                "professor": professor,
                "group_origin": existing_group,
                "group_new": new_group,
                "template_shortname": template,
            }
        return "create", {
            "reason": "different_professor_new_group",
            "professor": professor,
            "group_origin": existing_group,
            "group_new": new_group,
        }

    return "create", {"reason": "new", "professor": professor}
