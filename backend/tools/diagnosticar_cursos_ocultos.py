"""Diagnóstico y activación de cursos ocultos por identidad de profesor.

Detecta los cursos ocultos planificados con ``old_shortname == shortname``
(``planned_course_hidden_and_created``) y clasifica cada uno según el estado
del profesor ETL en Moodle (resuelto, creado, reutilizado, desconocido).

Uso:
  python tools/diagnose_hidden_courses.py --execution-id 3            # diagnóstico
  python tools/diagnose_hidden_courses.py --execution-id 3 --csv out.csv
  python tools/diagnose_hidden_courses.py --execution-id 3 --activate-only-matching

Con ``--activate-only-matching`` se activa (visible=1) únicamente los cursos
cuyo profesor ETL tiene un usuario real (resuelto/creado/reutilizado), dejando
intactos los de identidad desconocida.
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.sesion import SessionLocal
from app.services.fabrica_moodle import obtener_servicio_moodle


def _load_logs(db, execution_id: int):
    from sqlalchemy import text

    rows = db.execute(
        text(
            """
            WITH p430 AS (
                SELECT DISTINCT
                    p.identificador AS sn,
                    p.detalle->>'new_professor' AS etl_prof,
                    p.detalle->>'old_professor' AS old_prof,
                    h.detalle->>'fullname'      AS fullname,
                    h.creado_en                 AS hidden_at
                FROM registros_ejecucion p
                JOIN registros_ejecucion h
                  ON h.ejecucion_id = :eid AND h.accion = 'course_hidden'
                 AND h.identificador = p.identificador
                WHERE p.ejecucion_id = :eid
                  AND p.accion = 'planned_course_hidden_and_created'
                  AND p.detalle->>'old_shortname' = p.identificador
            ),
            resolved AS (
                SELECT identificador AS u, 'resolved' AS st
                FROM registros_ejecucion WHERE ejecucion_id = :eid AND accion = 'user_resolved'
            ),
            created AS (
                SELECT identificador AS u, 'created' AS st
                FROM registros_ejecucion
                WHERE ejecucion_id = :eid
                  AND accion IN ('user_created', 'user_created_createpassword')
            ),
            reused AS (
                SELECT identificador AS u, 'reused' AS st
                FROM registros_ejecucion
                WHERE ejecucion_id = :eid AND accion = 'user_reused_by_email'
            )
            SELECT
                p.sn,
                p.etl_prof,
                p.old_prof,
                p.fullname,
                COALESCE(r.u, c.u, k.u) AS real_username,
                COALESCE(r.st, c.st, k.st, 'unknown') AS estado_user
            FROM p430 p
            LEFT JOIN resolved r ON r.u = p.etl_prof
            LEFT JOIN created  c ON c.u = p.etl_prof
            LEFT JOIN reused   k ON k.u = p.etl_prof
            ORDER BY p.etl_prof, p.sn
            """
        ),
        {"eid": execution_id},
    )
    return [dict(row._mapping) for row in rows]


def _activate(modalidad: str, shortnames: list[str], batch: int = 25):
    async def _run():
        ms = obtener_servicio_moodle(modalidad)
        try:
            all_courses = await ms.obtener_cursos()
            sn_to_id = {
                c.get("shortname"): int(c["id"])
                for c in all_courses
                if c.get("shortname") and c.get("id")
            }
            resolved = [(sn_to_id[sn], sn) for sn in shortnames if sn in sn_to_id]
            not_found = [sn for sn in shortnames if sn not in sn_to_id]

            print(f"Activando {len(resolved)} cursos, {len(not_found)} no encontrados")
            updated = 0
            for i in range(0, len(resolved), batch):
                chunk = resolved[i : i + batch]
                params = {}
                for j, (cid, _) in enumerate(chunk):
                    params[f"courses[{j}][id]"] = cid
                    params[f"courses[{j}][visible]"] = 1
                await ms._request("core_course_update_courses", params, use_post=True)
                updated += len(chunk)
                print(f"  progreso: {updated}/{len(resolved)}")
            print(f"DONE: {updated} cursos activados")
            if not_found:
                print(f"  No encontrados en Moodle: {not_found[:20]}")
        finally:
            await ms.close()

    asyncio.run(_run())


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico/activación de cursos ocultos")
    parser.add_argument("--execution-id", type=int, required=True)
    parser.add_argument("--csv", default="", help="Ruta CSV de salida (opcional)")
    parser.add_argument(
        "--activate-only-matching",
        action="store_true",
        help="Activa solo cursos cuyo profesor tiene usuario real",
    )
    parser.add_argument(
        "--activate-all",
        action="store_true",
        help="Activa todos los cursos ocultos del diagnóstico",
    )
    parser.add_argument("--modalidad", default="DISTANCIA", help="Token de modalidad")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = _load_logs(db, args.execution_id)
    finally:
        db.close()

    print(f"Total cursos ocultos por identidad: {len(rows)}")
    from collections import Counter

    by_state = Counter(r["estado_user"] for r in rows)
    for st, n in by_state.most_common():
        print(f"  {st}: {n}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "sn",
                    "etl_prof",
                    "old_prof",
                    "fullname",
                    "real_username",
                    "estado_user",
                ],
            )
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        print(f"CSV escrito: {args.csv}")

    if args.activate_only_matching:
        to_activate = [
            r["sn"] for r in rows if r["estado_user"] in ("resolved", "created", "reused")
        ]
        print(f"Cursos con profesor real (a activar): {len(to_activate)}")
        if to_activate:
            _activate(args.modalidad, to_activate)

    if args.activate_all:
        to_activate = [r["sn"] for r in rows]
        print(f"Cursos a activar (todos): {len(to_activate)}")
        if to_activate:
            _activate(args.modalidad, to_activate)

    if not args.csv and not args.activate_only_matching and not args.activate_all:
        print("\nPrimeros 10:")
        for r in rows[:10]:
            print(
                f"  {r['sn']} | {r['etl_prof']} | {r['estado_user']} | {r['real_username'] or ''}"
            )


if __name__ == "__main__":
    main()
