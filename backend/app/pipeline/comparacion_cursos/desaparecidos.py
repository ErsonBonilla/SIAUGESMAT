from app.pipeline.comparacion_cursos.umbrales import (
    EDAD_MAXIMA_CURSO_SEGUNDOS,
)
from app.pipeline.comparacion_cursos.utilidades import (
    construir_clave_base,
    es_curso_oculto,
    obtener_edad_curso_segundos,
)
from app.pipeline.nombres_cortos import parsear_shortname


def encontrar_cursos_desaparecidos(
    existing_by_shortname: dict[str, dict],
    existing_by_base_key: dict[tuple[str, ...], list[dict]],
    new_shortnames: set,
    new_base_keys: set,
    new_program_codes: set[str],
    to_delete: list[str],
    to_hide: list[str],
    alerts: list[dict],
    logs: list[dict],
    *,
    max_age_seconds: int = EDAD_MAXIMA_CURSO_SEGUNDOS,
):
    for sn, existing in existing_by_shortname.items():
        if sn in new_shortnames:
            continue

        parsed = parsear_shortname(sn)
        if parsed:
            if parsed["cod_prog"] not in new_program_codes:
                continue
            base_key = construir_clave_base(parsed)
            if base_key in new_base_keys:
                continue

        age = obtener_edad_curso_segundos(existing)
        if age >= max_age_seconds:
            to_delete.append(
                {
                    "shortname": sn,
                    "reason": "disappeared",
                    "age_seconds": age,
                    "fullname": existing.get("fullname", ""),
                }
            )
            alerts.append(
                {
                    "shortname": sn,
                    "reason": "disappeared",
                    "age_seconds": age,
                }
            )
            logs.append(
                {
                    "phase": "2",
                    "action": "course_deleted",
                    "identifier": sn,
                    "detail": {"reason": "disappeared", "age_seconds": age},
                }
            )
        elif not es_curso_oculto(existing):
            to_hide.append(
                {
                    "shortname": sn,
                    "reason": "disappeared_recent",
                    "age_seconds": age,
                    "fullname": existing.get("fullname", ""),
                }
            )
            alerts.append(
                {
                    "shortname": sn,
                    "reason": "disappeared_recent",
                    "age_seconds": age,
                }
            )
            logs.append(
                {
                    "phase": "2",
                    "action": "course_disappeared_recent_hidden",
                    "identifier": sn,
                    "detail": {"reason": "disappeared_recent", "age_seconds": age},
                }
            )
