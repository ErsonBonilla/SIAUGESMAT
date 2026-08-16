"""Corrige usernames de cuentas duplicadas por email usando un CSV.

Lee un CSV con columnas `username, fecha_creacion, email` (típicamente la
consulta de correos duplicados de Moodle: una fila por cuenta). Para cada
correo con dos cuentas conserva la cuenta MÁS ANTIGUA por fecha de creación
(la que tiene datos e historial), le asigna el username de la cuenta MÁS
RECIENTE (el deseado) y elimina la cuenta más reciente. La eliminación es
incondicional (aunque la cuenta reciente tenga cursos); el número de cursos
del proceso queda registrado en el CSV de resultado como dato informativo.

Es el mismo patrón de backend/tools/restore_original_usernames.py y
backend/tools/fix_external_auth_users.py: auditar en solo lectura y aplicar
solo con un flag explícito.

Modos:
  --audit            Clasifica cada par contra Moodle (solo lectura).
  --fix              Aplica renombrado + borrado de los pares seguros.
  --csv PATH         CSV de entrada (default: Corregir username.csv del repo).
  --output PATH      CSV de resultado (default: junto al CSV de entrada).

Ejemplo:
  python tools/fix_duplicate_email_usernames.py --modalidad DISTANCIA --audit
  python tools/fix_duplicate_email_usernames.py --modalidad DISTANCIA --fix
"""

import argparse
import asyncio
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.pipeline.duplicate_emails import DuplicateGroup, group_rows
from app.services.moodle_factory import get_moodle_service

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = SCRIPT_DIR.parents[1] / "Corregir username.csv"
BATCH_SIZE = 50
TEMP_PREFIX = "zzdel_"
MAX_USERNAME_LEN = 100


# ---------------------------------------------------------------------------
# Moodle API helpers
# ---------------------------------------------------------------------------
async def _get_users_batch(ms, usernames: list) -> list:
    """core_user_get_users_by_field por username en lote."""
    if not usernames:
        return []
    params = {"field": "username"}
    for i, u in enumerate(usernames):
        params[f"values[{i}]"] = u
    try:
        result = await ms._request(
            "core_user_get_users_by_field",
            params,
            use_post=True,
            timeout=60.0,
        )
        if isinstance(result, list):
            return result
    except Exception as e:
        logger.exception(f"Error en get_users_batch: {e}")
    return []


async def _rename_user(ms, user_id: int, username: str) -> bool:
    try:
        await ms._request(
            "core_user_update_users",
            params={
                "users[0][id]": user_id,
                "users[0][username]": username,
            },
            use_post=True,
            timeout=30.0,
        )
        return True
    except Exception as e:
        logger.exception(f"  Fallo al renombrar id={user_id} -> {username}: {e}")
        return False


async def _delete_user(ms, user_id: int) -> bool:
    try:
        await ms._request(
            "core_user_delete_users",
            params={"userids[0]": user_id},
            use_post=True,
            timeout=30.0,
        )
        return True
    except Exception as e:
        logger.exception(f"  Fallo al eliminar userid={user_id}: {e}")
        return False


async def _get_user_courses(ms, user_id: int) -> list:
    """Cursos en los que el usuario está matriculado."""
    try:
        result = await ms._request(
            "core_enrol_get_users_courses",
            {"userid": user_id},
            timeout=30.0,
        )
        if isinstance(result, list):
            return result
    except Exception:
        pass
    return []


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------
def _temp_username(target: str) -> str:
    """Username temporal que libera el deseado antes de borrar el duplicado."""
    suffix = f"{TEMP_PREFIX}{target}"
    return suffix[:MAX_USERNAME_LEN]


async def build_plan(ms, csv_path) -> list[dict]:
    """Consulta Moodle y clasifica cada par por email."""
    csv_path = Path(csv_path)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    groups = group_rows(rows)
    print(f"\n  {len(groups)} emails con cuentas agrupadas desde {csv_path.name}\n")

    usernames = sorted({r.username for g in groups for r in g.rows})
    state: dict = {}
    for i in range(0, len(usernames), BATCH_SIZE):
        batch = usernames[i : i + BATCH_SIZE]
        for u in await _get_users_batch(ms, batch):
            state[u.get("username")] = u

    plans: list[dict] = []
    for group in groups:
        plan = _classify_group(group, state)
        if plan["status"] == "SEGURO":
            newer_user = plan["newer_user"]
            courses = await _get_user_courses(ms, newer_user["id"])
            plan["cursos_duplicado"] = len(courses)
        plans.append(plan)
    return plans


def _classify_group(group: DuplicateGroup, state: dict) -> dict:
    plan: dict = {"group": group, "detail": ""}

    if group.count != 2:
        plan["status"] = "REVISION_MANUAL"
        plan["detail"] = f"{group.count} cuentas para el mismo correo"
        return plan

    older = group.oldest()
    newer = group.newest()
    if older is None or newer is None:
        plan["status"] = "AMBIGUO"
        plan["detail"] = "fecha de creación no interpretable"
        return plan
    if older.date == newer.date:
        plan["status"] = "AMBIGUO"
        plan["detail"] = f"misma fecha de creación ({older.date.date()})"
        return plan

    older_user = state.get(older.username)
    newer_user = state.get(newer.username)
    plan["older"] = older
    plan["newer"] = newer
    plan["target"] = newer.username
    plan["cursos_duplicado"] = 0

    if older_user is None:
        plan["status"] = "FALTA_ANTIGUA"
        plan["detail"] = f"no existe en Moodle '{older.username}'"
        return plan
    if newer_user is None:
        plan["status"] = "FALTA_RECIENTE"
        plan["detail"] = f"no existe en Moodle '{newer.username}'"
        return plan

    plan["older_user"] = older_user
    plan["newer_user"] = newer_user

    if older.username == newer.username:
        plan["status"] = "YA_IGUAL"
        return plan

    target_holder = state.get(newer.username)
    if target_holder is None or target_holder.get("id") != newer_user.get("id"):
        plan["status"] = "CONFLICTO"
        plan["detail"] = f"username deseado '{newer.username}' lo ocupa otra cuenta"
        return plan

    plan["status"] = "SEGURO"
    return plan


# ---------------------------------------------------------------------------
# Auditoría (solo lectura)
# ---------------------------------------------------------------------------
async def run_audit(ms, plans: list[dict]):
    counts: dict = {}
    for plan in plans:
        counts.setdefault(plan["status"], []).append(plan)

    for status, label in [
        ("SEGURO", "Seguro: renombrar antigua + eliminar reciente"),
        ("AMBIGUO", "Misma fecha / fecha no interpretable (revisión manual)"),
        ("CONFLICTO", "Username deseado ocupado por otra cuenta (revisión manual)"),
        ("FALTA_ANTIGUA", "Cuenta antigua no encontrada en Moodle"),
        ("FALTA_RECIENTE", "Cuenta reciente no encontrada en Moodle"),
        ("YA_IGUAL", "Ambos usernames ya son iguales"),
        ("REVISION_MANUAL", "Número de cuentas distinto de 2"),
    ]:
        items = counts.get(status, [])
        print(f"  [{status}] {label}: {len(items)}")
        for plan in items:
            g = plan["group"]
            detail = f"  {plan['detail']}" if plan.get("detail") else ""
            print(f"    {g.email:<42}{detail}")
        print()

    safe = len(counts.get("SEGURO", []))
    print(f"  >>> {safe} pares listos para --fix (renombrar antigua + eliminar reciente)")
    print(f"  >>> {len(plans) - safe} requieren revisión manual\n")


# ---------------------------------------------------------------------------
# Fix: aplicar renombrado + borrado
# ---------------------------------------------------------------------------
async def run_fix(ms, plans: list[dict]):
    to_fix = [p for p in plans if p["status"] == "SEGURO"]

    if not to_fix:
        print("  No hay pares por corregir (usa --audit para ver la clasificación).\n")
        return

    print(f"\n  Corrigiendo {len(to_fix)} pares...\n")
    ok = fail = 0
    for i, plan in enumerate(to_fix, 1):
        g = plan["group"]
        target = plan["target"]
        older_user = plan["older_user"]
        newer_user = plan["newer_user"]
        newer_original = newer_user.get("username")
        temp = _temp_username(target)
        print(f"  [{i}/{len(to_fix)}] {g.email}")
        print(f"      renombrar '{g.oldest().username}' -> '{target}'")

        if not await _rename_user(ms, newer_user["id"], temp):
            print(f"      [FAIL] no se pudo liberar '{target}' ({newer_original} -> {temp})")
            plan["detail"] = "falló liberación del username"
            fail += 1
            continue

        if not await _rename_user(ms, older_user["id"], target):
            print(f"      [FAIL] no se pudo renombrar '{older_user.get('username')}' -> '{target}'")
            await _rename_user(ms, newer_user["id"], newer_original)
            plan["detail"] = "falló el renombrado de la cuenta conservada"
            fail += 1
            continue

        if not await _delete_user(ms, newer_user["id"]):
            print(
                f"      [WARN] cuenta duplicada no eliminada (queda como '{temp}'); "
                "renombrado aplicado"
            )
            plan["detail"] = "renombrado OK, duplicado no eliminado"
            plan["status"] = "ELIMINACION_PENDIENTE"
            ok += 1
            continue

        print("      [OK] renombrado + duplicado eliminado")
        plan["detail"] = "OK"
        plan["status"] = "CORREGIDO"
        ok += 1

    print(f"\n  Correctos:  {ok}")
    print(f"  Fallidos:   {fail}\n")


# ---------------------------------------------------------------------------
# CSV de resultado
# ---------------------------------------------------------------------------
def write_result(csv_path: Path, plans: list[dict], output_path: Path | None):
    if not output_path:
        output_path = csv_path.with_name(f"{csv_path.stem}_resultado.csv")

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "email",
                "username_conservado",
                "username_asignado",
                "fecha_antigua",
                "fecha_reciente",
                "estado",
                "detalle",
                "cursos_duplicado",
            ],
        )
        writer.writeheader()
        for plan in plans:
            g = plan["group"]
            older = g.oldest()
            newer = g.newest()
            writer.writerow(
                {
                    "email": g.email,
                    "username_conservado": older.username if older else "",
                    "username_asignado": plan.get("target", ""),
                    "fecha_antigua": _fmt_fecha(older),
                    "fecha_reciente": _fmt_fecha(newer),
                    "estado": plan["status"],
                    "detalle": plan.get("detail", ""),
                    "cursos_duplicado": plan.get("cursos_duplicado", ""),
                }
            )
    print(f"  CSV de resultado: {output_path}\n")


def _fmt_fecha(user_row) -> str:
    if user_row is None or user_row.date is None:
        return ""
    return datetime.strftime(user_row.date, "%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(
        description="Corrige usernames de cuentas duplicadas por email (conserva la más antigua)"
    )
    parser.add_argument("--modalidad", default="DISTANCIA", help="Modalidad (DISTANCIA/PRESENCIAL)")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="CSV de entrada (username,fecha_creacion,email)",
    )
    parser.add_argument("--audit", action="store_true", help="Clasificar los pares (solo lectura)")
    parser.add_argument("--fix", action="store_true", help="Aplicar renombrado + borrado")
    parser.add_argument(
        "--output", type=Path, default=None, help="CSV de resultado (default: junto al de entrada)"
    )
    args = parser.parse_args()

    print(f"\n=== fix_duplicate_email_usernames | modalidad={args.modalidad} ===\n")

    if not args.csv.exists():
        print(f"  ERROR: No se encontró {args.csv}")
        sys.exit(1)

    ms = get_moodle_service(args.modalidad)

    try:
        plans = await build_plan(ms, args.csv)

        if args.audit or not args.fix:
            await run_audit(ms, plans)
            if not args.fix:
                print("  Usa --fix para aplicar los cambios (o --audit para solo lectura).\n")
                write_result(args.csv, plans, args.output)
                return

        if args.fix:
            await run_fix(ms, plans)
            write_result(args.csv, plans, args.output)

    finally:
        await ms.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
