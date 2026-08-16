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

from app.db.session import SessionLocal
from app.services.moodle_factory import get_moodle_service


def _load_logs(db, execution_id: int):
    from sqlalchemy import text

    rows = db.execute(
        text(
            """
            WITH p430 AS (
                SELECT DISTINCT
                    p.identifier AS sn,
                    p.detail->>'new_professor' AS etl_prof,
                    p.detail->>'old_professor' AS old_prof,
                    h.detail->>'fullname'      AS fullname,
                    h.created_at               AS hidden_at
                FROM execution_logs p
                JOIN execution_logs h
                  ON h.execution_id = :eid AND h.action = 'course_hidden'
                 AND h.identifier = p.identifier
                WHERE p.execution_id = :eid
                  AND p.action = 'planned_course_hidden_and_created'
                  AND p.detail->>'old_shortname' = p.identifier
            ),
            resolved AS (
                SELECT identifier AS u, 'resolved' AS st
                FROM execution_logs WHERE execution_id = :eid AND action = 'user_resolved'
            ),
            created AS (
                SELECT identifier AS u, 'created' AS st
                FROM execution_logs
                WHERE execution_id = :eid
                  AND action IN ('user_created', 'user_created_createpassword')
            ),
            reused AS (
                SELECT identifier AS u, 'reused' AS st
                FROM execution_logs
                WHERE execution_id = :eid AND action = 'user_reused_by_email'
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
        ms = get_moodle_service(modalidad)
        try:
            all_courses = await ms.get_courses()
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
