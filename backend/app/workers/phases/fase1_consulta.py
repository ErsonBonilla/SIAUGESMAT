import logging

from app.pipeline.categorias import obtener_ids_subarbol_idead
from app.pipeline.nombres_cortos import SIAUGESMAT_PATTERN
from app.pipeline.usuarios import (
    buscar_candidatos_docente,
    indexar_docentes,
    resolver_usuarios,
)
from app.repositories import repositorio_registros
from app.repositories.repositorio_ejecuciones import actualizar_heartbeat, actualizar_progreso
from app.services.mensajes_error import traducir_error
from app.workers.phases.base import ContextoFase, FaseBase

logger = logging.getLogger(__name__)


class FaseConsulta(FaseBase):
    nombre_fase = "1"

    async def ejecutar(self, ctx: ContextoFase) -> None:
        db = ctx.db
        eid = ctx.ejecucion_id
        mode = ctx.modo
        etl_data = ctx.datos_etl
        moodle_service = ctx.servicio_moodle
        integration = ctx.integracion

        try:
            actualizar_progreso(db, eid, 2, "Consultando categorías…", paso=1)

            all_moodle_cats = await moodle_service.obtener_categorias()
            ids_idead = obtener_ids_subarbol_idead(all_moodle_cats)
            cats_idead = [c for c in all_moodle_cats if int(c.get("id") or 0) in ids_idead]
            ctx.mapa_todas_categorias = {
                c.get("idnumber", ""): c for c in cats_idead if c.get("idnumber")
            }
            ctx.idnumeros_categorias_existentes = set(ctx.mapa_todas_categorias.keys())

            actualizar_progreso(db, eid, 5, "Consultando cursos…")

            all_courses = await moodle_service.obtener_cursos()
            if not isinstance(all_courses, list):
                raise ValueError(
                    f"obtener_cursos() devolvió {type(all_courses).__name__} "
                    f"en vez de list: {str(all_courses)[:200]}"
                )
            ctx.cursos_existentes = [
                c
                for c in all_courses
                if int(c.get("categoryid") or c.get("category") or 0) in ids_idead
                and SIAUGESMAT_PATTERN.match(c.get("shortname", ""))
            ]

            actualizar_progreso(db, eid, 10, "Consultando usuarios…")

            etl_users = etl_data["users"]

            all_institutional = {
                u["email"]
                for u in etl_users
                if u.get("email") and str(u["email"]).strip().lower().endswith("@ut.edu.co")
            }

            def _persistir_conflictos_correo(integration=None):
                conflicts = getattr(integration, "ultimos_conflictos_correo", [])
                for conflict in conflicts:
                    repositorio_registros.guardar_log(
                        db,
                        eid,
                        "1",
                        "identity_by_email_duplicate",
                        conflict.get("email", ""),
                        {
                            "usernames": conflict.get("usernames", []),
                            "selected": conflict.get("selected", ""),
                            "selected_id": conflict.get("selected_id"),
                            "renamed": conflict.get("renamed", ""),
                            "deleted": conflict.get("deleted", []),
                            "pending_review": conflict.get("pending_review", []),
                            "auth_switched": conflict.get("auth_switched", False),
                            "auth_reason": conflict.get("auth_reason", ""),
                            "criterion": "oldest",
                        },
                    )

            institutional_map = (
                await integration.encontrar_usuarios_por_correos(list(all_institutional))
                if all_institutional
                else {}
            )
            _persistir_conflictos_correo(integration)

            username_emails: dict[str, str] = {}
            for u in etl_users:
                if u.get("username") and u.get("email"):
                    username_emails[u["username"]] = u["email"]
            for user in institutional_map.values():
                uname = user.get("username", "")
                email = user.get("email", "")
                if uname and email:
                    username_emails[uname] = email
            ctx.correos_usuarios = username_emails

            username_map, user_events = resolver_usuarios(
                etl_users,
                institutional_map,
            )
            for tipo, identifier, detail in user_events:
                if tipo == "user_resolved" and mode not in ("users", "both"):
                    continue
                repositorio_registros.guardar_log(db, eid, "1", tipo, identifier, detail)
                if tipo == "user_identity_conflict":
                    logger.warning(
                        f"Conflicto de identidad {identifier}: ETL='{detail['etl_fullname']}' "
                        f"vs Moodle='{detail['moodle_fullname']}' "
                        f"(match por {detail['matched_by']})"
                    )
            ctx.mapa_usuarios = username_map

            courses_by_sn = {
                c["shortname"]: c.get("fullname", "") for c in etl_data.get("courses", [])
            }
            for dup in etl_data.get("duplicates", []):
                repositorio_registros.guardar_log(
                    db,
                    eid,
                    "1",
                    "duplicate_email",
                    dup["email"],
                    {
                        "usernames": dup.get("username", ""),
                        "course": dup.get("course_shortname", ""),
                        "fullname": courses_by_sn.get(dup.get("course_shortname", ""), ""),
                    },
                )

            repositorio_registros.guardar_log(
                db,
                eid,
                "1",
                "phase1_complete",
                detalle={
                    "categories_found": len(ctx.idnumeros_categorias_existentes),
                    "courses_found": len(ctx.cursos_existentes),
                    "users_resolved": len(username_map),
                },
            )
            logger.info(
                f"FASE 1: {len(ctx.idnumeros_categorias_existentes)} cats, "
                f"{len(ctx.cursos_existentes)} cursos, "
                f"{len(username_map)} usuarios resueltos"
            )
            actualizar_progreso(db, eid, 14, "Análisis de datos completado")

            courses_with_teacher: dict[str, str] = {}
            if mode in ("courses", "both"):
                teacher_index = indexar_docentes(etl_data["users"], etl_data["enrolments"])

                import asyncio

                sem = asyncio.Semaphore(10)

                async def _obtener_docente(c, idx):
                    sn = c.get("shortname", "")
                    emails, usernames, idnumbers = buscar_candidatos_docente(sn, teacher_index)
                    async with sem:
                        teachers = await moodle_service.obtener_docentes_matriculados(
                            int(c["id"]),
                            emails,
                            teacher_usernames=usernames,
                            teacher_idnumbers=idnumbers,
                        )
                    if idx > 0 and idx % 25 == 0:
                        actualizar_heartbeat(db, eid)
                    if teachers:
                        return sn, teachers[0].get("username", "")
                    return sn, None

                tasks = [_obtener_docente(c, i) for i, c in enumerate(ctx.cursos_existentes)]
                results = await asyncio.gather(*tasks)
                for sn, username in results:
                    if username:
                        courses_with_teacher[sn] = username
            ctx.cursos_con_docente = courses_with_teacher

            logger.info(
                f"FASE 1d: {len(courses_with_teacher)} cursos con editingteacher, "
                f"{len(ctx.cursos_existentes) - len(courses_with_teacher)} cursos huérfanos"
            )

        except Exception as e:
            logger.exception(f"Error en FASE 1 (consulta): {e}")
            repositorio_registros.guardar_error(db, eid, "1", "", traducir_error(e))
            ctx.metricas["total_errors"] += 1
            raise
