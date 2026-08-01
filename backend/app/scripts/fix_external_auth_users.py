"""Audita y repara usuarios de Moodle con auth externo.

Modos:
  --user USERNAME      Repara un usuario individual
  --audit              Auditoria masiva: busca enrolados recientes con auth != manual
  --fix | --fix-all    Aplica la reparacion (con --user o con --audit)
  --dedup              [PENDIENTE] Detectar y consolidar emails duplicados (Fase 3)

Ejemplos:
  # Auditoria masiva (solo lectura)
  python -m app.scripts.fix_external_auth_users --modalidad DISTANCIA --audit

  # Reparar todos los encontrados
  python -m app.scripts.fix_external_auth_users --modalidad DISTANCIA --audit --fix-all

  # Usuario individual
  python -m app.scripts.fix_external_auth_users --modalidad DISTANCIA --user lhgarzonr --fix
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.moodle_factory import get_moodle_service

logger = logging.getLogger(__name__)

INSTITUTIONAL_DOMAIN = settings.INSTITUTIONAL_EMAIL_DOMAIN
BATCH_SIZE = 100
FIX_BATCH_SIZE = 50


# ---------------------------------------------------------------------------
# Moodle API helpers
# ---------------------------------------------------------------------------
async def _get_users_batch(ms, usernames: list) -> list:
    """core_user_get_users_by_field en lote (retorna lista de dicts con auth)."""
    if not usernames:
        return []
    params = {"field": "username"}
    for i, u in enumerate(usernames):
        params[f"values[{i}]"] = u
    result = await ms._request(
        "core_user_get_users_by_field", params,
        use_post=True, timeout=60.0,
    )
    if isinstance(result, list):
        return result
    return []


async def _find_user_by_username(ms, username: str) -> dict | None:
    result = await ms._request(
        "core_user_get_users",
        params={"criteria[0][key]": "username", "criteria[0][value]": username},
        use_post=True, timeout=60.0,
    )
    if isinstance(result, dict):
        users = result.get("users", [])
        return users[0] if users else None
    return None


async def _fix_user_auth(ms, user: dict) -> bool:
    """Repara un usuario individual."""
    try:
        await ms._request("core_user_update_users", params={
            "users[0][id]": user["id"],
            "users[0][auth]": "manual",
        })
        return True
    except Exception as e:
        logger.error(f"  Fallo al reparar {user.get('username')} (id={user['id']}): {e}")
        return False


async def _fix_users_batch(ms, users: list) -> tuple:
    params = {}
    for i, user in enumerate(users):
        params[f"users[{i}][id]"] = user["id"]
        params[f"users[{i}][auth]"] = "manual"
    try:
        await ms._request("core_user_update_users", params, use_post=True, timeout=90.0)
        return len(users), 0
    except Exception as e:
        logger.error(f"  Fallo en lote de {len(users)} usuarios: {e}")
        # Fallback: uno por uno
        ok = fail = 0
        for user in users:
            if await _fix_user_auth(ms, user):
                ok += 1
            else:
                fail += 1
        return ok, fail


# ---------------------------------------------------------------------------
# App DB helpers
# ---------------------------------------------------------------------------
def _get_recent_enrolled_usernames(days: int = 15) -> list:
    """Usernames con enrolment_ok en los ultimos N dias."""
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT DISTINCT identifier FROM execution_logs "
            "WHERE action = 'enrolment_ok' "
            "AND created_at > NOW() - :interval * INTERVAL '1 day' "
            "ORDER BY identifier"
        ), {"interval": days}).fetchall()
        return [r[0] for r in rows]
    finally:
        db.close()


def _get_recent_created_usernames(days: int = 15) -> list:
    """Usernames con user_created_createpassword en los ultimos N dias."""
    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT DISTINCT identifier FROM execution_logs "
            "WHERE action = 'user_created_createpassword' "
            "AND created_at > NOW() - :interval * INTERVAL '1 day' "
            "ORDER BY identifier"
        ), {"interval": days}).fetchall()
        return [r[0] for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
def _print_user(user: dict, idx: int = 0):
    username = user.get("username", "?")
    email = (user.get("email") or "sin email").strip().lower()
    auth = user.get("auth", "?")
    fullname = f"{user.get('firstname','')} {user.get('lastname','')}".strip()
    prefix = f"   #{idx:<3}" if idx else "   "
    print(f"{prefix}{username:<20} {email:<35} auth={auth:<8} {fullname}")


# ---------------------------------------------------------------------------
# Audit + fix-all flow
# ---------------------------------------------------------------------------
async def _audit_and_fix(ms, usernames: list, fix_all: bool, days: int):
    if not usernames:
        print("   No hay usernames recientes en los logs del app.\n")
        return

    print(f"   {len(usernames)} usernames unicos enrolados en los ultimos {days} dias.\n")
    print(f"   Consultando Moodle en lotes de {BATCH_SIZE}...\n")

    affected = []

    for i in range(0, len(usernames), BATCH_SIZE):
        batch = usernames[i:i + BATCH_SIZE]
        try:
            users = await _get_users_batch(ms, batch)
        except Exception as e:
            print(f"   ERROR lote {i//BATCH_SIZE + 1}: {e}")
            continue
        for user in users:
            auth = user.get("auth", "")
            email = (user.get("email") or "").strip().lower()
            if auth != "manual" and email.endswith(INSTITUTIONAL_DOMAIN):
                affected.append(user)
        done = min(i + BATCH_SIZE, len(usernames))
        print(f"   [{done}/{len(usernames)}] procesados, {len(affected)} afectados hasta ahora")

    print()
    if not affected:
        print("   OK - Todos los usuarios recientes tienen auth=manual.\n")
        return

    # Agrupar por email para detectar duplicados
    by_email: dict = {}
    for u in affected:
        email = (u.get("email") or "").strip().lower()
        by_email.setdefault(email, []).append(u)

    dups = {e: us for e, us in by_email.items() if len(us) > 1}
    if dups:
        print(f"   ATENCION: {len(dups)} emails con multiples usuarios:\n")
        for email, users in dups.items():
            print(f"   Email: {email}")
            for u in users:
                _print_user(u, 0)
            print()

    print(f"   {len(affected)} usuarios institucionales con auth != manual:\n")
    for i, user in enumerate(affected, 1):
        _print_user(user, i)

    if not fix_all:
        print(f"\n>>> Se repararian {len(affected)} usuarios. Usa --fix-all para aplicar.\n")
        return

    print(f"\n   Aplicando reparacion en lotes de {FIX_BATCH_SIZE} ({len(affected)} usuarios)...\n")
    ok = fail = 0
    for i in range(0, len(affected), FIX_BATCH_SIZE):
        batch = affected[i:i + FIX_BATCH_SIZE]
        b_ok, b_fail = await _fix_users_batch(ms, batch)
        ok += b_ok
        fail += b_fail
        done = min(i + FIX_BATCH_SIZE, len(affected))
        print(f"   [{done}/{len(affected)}] OK={ok} FAIL={fail}")
    print(f"\n  Reparados: {ok}")
    print(f"  Fallidos:  {fail}\n")


# ---------------------------------------------------------------------------
# Dedup flow (Fase 3)
# ---------------------------------------------------------------------------
async def _get_user_courses(ms, user_id: int) -> list:
    """Cursos en los que el usuario esta enrolado."""
    try:
        result = await ms._request("core_enrol_get_users_courses", {
            "userid": user_id,
        }, timeout=30.0)
        if isinstance(result, list):
            return result
    except Exception:
        pass
    return []


async def _delete_users(ms, user_ids: list) -> bool:
    """Elimina usuarios fisicamente (core_user_delete_users)."""
    try:
        params = {}
        for i, uid in enumerate(user_ids):
            params[f"userids[{i}]"] = uid
        await ms._request("core_user_delete_users", params, use_post=True, timeout=60.0)
        return True
    except Exception as e:
        logger.error(f"  Error al eliminar usuarios: {e}")
        return False


async def _dedup_flow(ms, fix: bool, days: int):
    usernames = _get_recent_enrolled_usernames(days)
    if not usernames:
        print("   No hay usernames recientes en los logs del app.\n")
        return

    print(f"   {len(usernames)} usernames unicos enrolados en los ultimos {days} dias.\n")
    print(f"   Consultando Moodle en lotes de {BATCH_SIZE}...\n")

    all_users: list = []
    for i in range(0, len(usernames), BATCH_SIZE):
        batch = usernames[i:i + BATCH_SIZE]
        try:
            users = await _get_users_batch(ms, batch)
        except Exception as e:
            print(f"   ERROR lote {i//BATCH_SIZE + 1}: {e}")
            continue
        for user in users:
            email = (user.get("email") or "").strip().lower()
            if email.endswith(INSTITUTIONAL_DOMAIN):
                all_users.append(user)
        done = min(i + BATCH_SIZE, len(usernames))
        print(f"   [{done}/{len(usernames)}] procesados, {len(all_users)} institucionales")

    print()
    if not all_users:
        print("   OK - No se encontraron usuarios.\n")
        return

    # Agrupar por email
    by_email: dict = {}
    for u in all_users:
        email = (u.get("email") or "").strip().lower()
        by_email.setdefault(email, []).append(u)

    dups = {e: us for e, us in by_email.items() if len(us) > 1}
    if not dups:
        print("   OK - No hay emails duplicados entre los usuarios recientes.\n")
        return

    print(f"   {len(dups)} emails con multiples usuarios.\n")

    to_delete = []
    to_warn = []

    for email, users in dups.items():
        print(f"   Email: {email}")
        with_courses = []
        without_courses = []

        for u in users:
            courses = await _get_user_courses(ms, u["id"])
            u["_courses"] = len(courses)
            label = f"{u['username']} (id={u['id']}, cursos={u['_courses']}, firstaccess={u.get('firstaccess','?')})"
            print(f"      {label}")
            if courses:
                with_courses.append(u)
            else:
                without_courses.append(u)
        print()

        if len(with_courses) == 0:
            # Todos sin cursos: eliminar todos menos el mas antiguo
            all_sorted = sorted(users, key=lambda u: u.get("firstaccess", 0))
            keep = all_sorted[0]
            kill = [u for u in all_sorted[1:] if u != keep]
            if kill:
                to_delete.extend(kill)
                print(f"      -> Conservar: {keep['username']}")
                for u in kill:
                    print(f"      -> Eliminar: {u['username']} (sin cursos)")
        elif len(with_courses) == 1:
            # Uno con cursos: eliminar los demas sin cursos
            keep = with_courses[0]
            kill = [u for u in without_courses if u != keep]
            if kill:
                to_delete.extend(kill)
                print(f"      -> Conservar: {keep['username']} ({keep['_courses']} cursos)")
                for u in kill:
                    print(f"      -> Eliminar: {u['username']} (sin cursos)")
        else:
            # Varios con cursos: requiere decision manual
            to_warn.append((email, with_courses))
            print(f"      *** ATENCION: {len(with_courses)} usuarios con cursos. Requiere decision manual. ***")
        print()

    if to_warn:
        print(f"   *** {len(to_warn)} emails requieren decision manual (varios usuarios con cursos):\n")
        for email, users in to_warn:
            print(f"   {email}:")
            for u in users:
                print(f"      {u['username']} ({u['_courses']} cursos)")
            print()

    if not to_delete:
        print("   No hay usuarios seguros para eliminar (todos tienen cursos).\n")
        return

    print(f"   >>> {'DRY RUN' if not fix else 'ELIMINANDO'} - "
          f"{len(to_delete)} usuarios sin cursos:\n")
    for u in to_delete:
        email = (u.get("email") or "").strip().lower()
        print(f"      {u['username']:<20} id={u['id']:<6} {email}  (0 cursos)")

    if not fix:
        print(f"\n   Se eliminarian {len(to_delete)} usuarios. Usa --dedup --fix para aplicar.\n")
        return

    print(f"\n   Eliminando {len(to_delete)} usuarios...")
    all_ids = [u["id"] for u in to_delete]
    if await _delete_users(ms, all_ids):
        print(f"   [OK] {len(to_delete)} usuarios eliminados.\n")
    else:
        # Fallback: uno por uno
        ok = fail = 0
        for u in to_delete:
            if await _delete_users(ms, [u["id"]]):
                ok += 1
                print(f"   [OK] {u['username']}")
            else:
                fail += 1
                print(f"   [ERROR] {u['username']}")
        print(f"\n  Eliminados: {ok}")
        print(f"  Fallidos:  {fail}\n")
async def main():
    parser = argparse.ArgumentParser(
        description="Audita y repara usuarios de Moodle con auth externo"
    )
    parser.add_argument("--modalidad", default="DISTANCIA",
                        help="Modalidad (DISTANCIA/PRESENCIAL)")
    parser.add_argument("--user", type=str, default=None,
                        help="Reparar un usuario especifico por username")
    parser.add_argument("--fix", action="store_true",
                        help="Aplicar reparacion (con --user)")
    parser.add_argument("--audit", action="store_true",
                        help="Auditar enrolados recientes con auth != manual")
    parser.add_argument("--fix-all", action="store_true",
                        help="Reparar TODOS los encontrados en la auditoria")
    parser.add_argument("--days", type=int, default=15,
                        help="Dias hacia atras para la auditoria (default 15)")
    parser.add_argument("--dedup", action="store_true",
                        help="[PENDIENTE] Consolidar emails duplicados (Fase 3)")
    args = parser.parse_args()

    print(f"\n=== fix_external_auth_users | modalidad={args.modalidad} ===\n")

    ms = get_moodle_service(args.modalidad)

    try:
        # --- Modo usuario individual ---
        if args.user:
            username = args.user.strip()
            print(f"   Buscando usuario '{username}'...")
            user = await _find_user_by_username(ms, username)
            if not user:
                print(f"   ERROR: '{username}' no encontrado.\n")
                return
            auth = user.get("auth", "")
            if auth == "manual":
                print(f"   OK: '{username}' ya tiene auth=manual.\n")
                _print_user(user)
                return
            print(f"   Encontrado con auth={auth}.")
            if not args.fix:
                _print_user(user)
                print(f"\n   Usa --fix para reparar.\n")
                return
            _print_user(user)
            print(f"\n   Cambiando auth={auth} -> manual...")
            if await _fix_user_auth(ms, user):
                print(f"   [OK] {username} reparado.\n")
            else:
                print(f"   [ERROR] No se pudo reparar {username}.\n")
            return

        # --- Modo auditoria masiva ---
        if args.audit:
            usernames = _get_recent_enrolled_usernames(args.days)
            await _audit_and_fix(ms, usernames, args.fix_all, args.days)
            return

        # --- Modo dedup ---
        if args.dedup:
            await _dedup_flow(ms, args.fix, args.days)
            return

        print("   Usa --audit para auditoria masiva,")
        print("   o --user USERNAME para un usuario individual.\n")

    finally:
        await ms.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
