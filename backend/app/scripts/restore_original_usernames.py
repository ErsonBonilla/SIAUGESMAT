"""Restaura usernames originales de Moodle renombrados por el bug del ETL.

El bug renombro cuentas existentes con auth=manual cuyo username en Moodle
difería del email-prefix (username_esperado). Los pares (old -> new) fueron
capturados de los logs del worker y persisitidos en data/renamed_usernames.tsv.

Modos:
  --audit             Clasifica los 128 pares (solo lectura).
  --fix               Aplica renombramiento de vuelta (safe + auth-fix).
  --recreate-gone     Recrea las 3 cuentas eliminadas + re-matricula.
  --conflicts-fix     Fija auth=manual en conflictos y re-matricula (conserva orig).
  --csv               Genera CSV de notificacion para docentes.
"""

import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

from app.core.config import settings
from app.services.moodle_factory import get_moodle_service

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "data" / "renamed_usernames.tsv"
BATCH_SIZE = 50
EDITINGTEACHER_ROLEID = 3


# ---------------------------------------------------------------------------
# Moodle API helpers
# ---------------------------------------------------------------------------
async def _get_users_batch(ms, usernames: list, timeout: float = 60.0) -> list:
    if not usernames:
        return []
    params = {"field": "username"}
    for i, u in enumerate(usernames):
        params[f"values[{i}]"] = u
    try:
        result = await ms._request(
            "core_user_get_users_by_field", params,
            use_post=True, timeout=timeout,
        )
        if isinstance(result, list):
            return result
    except Exception as e:
        logger.error(f"Error en get_users_batch: {e}")
    return []


async def _find_user_by_username(ms, username: str) -> dict | None:
    try:
        result = await ms._request(
            "core_user_get_users",
            params={"criteria[0][key]": "username", "criteria[0][value]": username},
            use_post=True, timeout=60.0,
        )
        if isinstance(result, dict):
            users = result.get("users", [])
            return users[0] if users else None
    except Exception as e:
        logger.error(f"Error buscando usuario {username}: {e}")
    return None


async def _update_user_username(ms, user_id: int, username: str) -> bool:
    try:
        await ms._request("core_user_update_users", params={
            "users[0][id]": user_id,
            "users[0][username]": username,
        }, use_post=True, timeout=30.0)
        return True
    except Exception as e:
        logger.error(f"  Fallo al renombrar id={user_id} -> {username}: {e}")
        return False


async def _update_user_auth(ms, user_id: int, auth: str = "manual") -> bool:
    try:
        await ms._request("core_user_update_users", params={
            "users[0][id]": user_id,
            "users[0][auth]": auth,
        }, use_post=True, timeout=30.0)
        return True
    except Exception as e:
        logger.error(f"  Fallo al fijar auth={auth} para id={user_id}: {e}")
        return False


async def _update_batch_auth(ms, users: list) -> tuple:
    params = {}
    for i, user in enumerate(users):
        params[f"users[{i}][id]"] = user["id"]
        params[f"users[{i}][auth]"] = "manual"
    try:
        await ms._request("core_user_update_users", params, use_post=True, timeout=90.0)
        return len(users), 0
    except Exception as e:
        logger.error(f"  Fallo en lote de {len(users)} usuarios: {e}")
        ok = fail = 0
        for user in users:
            if await _update_user_auth(ms, user["id"]):
                ok += 1
            else:
                fail += 1
        return ok, fail


async def _create_user(ms, username: str, email: str, firstname: str,
                       lastname: str) -> dict | None:
    params = {
        "users[0][username]": username,
        "users[0][email]": email,
        "users[0][firstname]": firstname,
        "users[0][lastname]": lastname,
        "users[0][auth]": "manual",
        "users[0][createpassword]": 1,
    }
    try:
        result = await ms._request("core_user_create_users", params,
                                   use_post=True, timeout=30.0)
        if isinstance(result, list) and result:
            return result[0]
    except Exception as e:
        logger.error(f"  Fallo al crear usuario {username}: {e}")
    return None


async def _get_course_id(ms, shortname: str) -> int | None:
    try:
        result = await ms._request("core_course_get_courses_by_field", params={
            "field": "shortname",
            "value": shortname,
        }, timeout=30.0)
        if isinstance(result, dict):
            courses = result.get("courses", [])
            if courses:
                return int(courses[0]["id"])
    except Exception:
        pass
    return None


async def _enrol_user(ms, user_id: int, course_id: int, role_id: int = 3) -> bool:
    try:
        await ms._request("enrol_manual_enrol_users", params={
            "enrolments[0][userid]": user_id,
            "enrolments[0][courseid]": course_id,
            "enrolments[0][roleid]": role_id,
        }, use_post=True, timeout=30.0)
        return True
    except Exception as e:
        logger.error(f"  Fallo al matricular userid={user_id} en courseid={course_id}: {e}")
        return False


async def _delete_user_by_id(ms, user_id: int) -> bool:
    try:
        await ms._request("core_user_delete_users", params={
            "userids[0]": user_id,
        }, use_post=True, timeout=30.0)
        return True
    except Exception as e:
        logger.error(f"  Fallo al eliminar userid={user_id}: {e}")
        return False


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
def load_pairs() -> list:
    if not DATA_FILE.exists():
        print(f"ERROR: No se encontro {DATA_FILE}")
        sys.exit(1)
    pairs = []
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 8:
                continue
            pairs.append({
                "old": parts[0],
                "new": parts[1],
                "email": parts[2],
                "firstname": parts[3],
                "lastname": parts[4],
                "cedula": parts[5],
                "email_personal": parts[6],
                "courses": [c for c in parts[7].split(",") if c],
            })
    return pairs


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
async def classify_all(ms, pairs: list) -> list:
    """Consulta Moodle para cada par y clasifica: SAFE, AUTH_FIX, CONFLICT, GONE, ALREADY_OK."""
    all_news = [p["new"] for p in pairs]
    all_olds = [p["old"] for p in pairs]

    new_state = {}
    for i in range(0, len(all_news), BATCH_SIZE):
        batch = all_news[i:i + BATCH_SIZE]
        users = await _get_users_batch(ms, batch)
        for u in users:
            new_state[u.get("username")] = u

    old_state = {}
    for i in range(0, len(all_olds), BATCH_SIZE):
        batch = all_olds[i:i + BATCH_SIZE]
        users = await _get_users_batch(ms, batch)
        for u in users:
            old_state[u.get("username")] = u

    results = []
    for p in pairs:
        new_user = new_state.get(p["new"])
        old_user = old_state.get(p["old"])
        if new_user and not old_user:
            if new_user.get("auth") == "manual":
                results.append({"pair": p, "status": "SAFE_RENAME", "new_user": new_user})
            else:
                results.append({"pair": p, "status": "AUTH_FIX_RENAME", "new_user": new_user})
        elif new_user and old_user:
            results.append({"pair": p, "status": "CONFLICT", "new_user": new_user, "old_user": old_user})
        elif not new_user and old_user:
            results.append({"pair": p, "status": "ALREADY_OK", "old_user": old_user})
        else:
            results.append({"pair": p, "status": "GONE"})
    return results


# ---------------------------------------------------------------------------
# Audit / Read-only
# ---------------------------------------------------------------------------
async def run_audit(ms, pairs: list):
    print(f"\n  Clasificando {len(pairs)} pares contra Moodle...\n")
    classified = await classify_all(ms, pairs)

    counts = {}
    for c in classified:
        counts.setdefault(c["status"], []).append(c)

    for status, label in [
        ("SAFE_RENAME", "Restaurar seguro (new existe, old libre, auth=manual)"),
        ("AUTH_FIX_RENAME", "Requiere fix auth=db primero, luego renombrar"),
        ("CONFLICT", "Conflicto: ambos usernames existen (revision manual)"),
        ("ALREADY_OK", "Ya en username original (new no existe, old si)"),
        ("GONE", "Cuenta eliminada (ni new ni old existen)"),
    ]:
        items = counts.get(status, [])
        print(f"  [{status}] {label}: {len(items)}")
        if items and status in ("CONFLICT", "GONE", "ALREADY_OK", "AUTH_FIX_RENAME"):
            for item in items:
                p = item["pair"]
                nu = item.get("new_user")
                ou = item.get("old_user")
                parts = [f"    {p['old']} -> {p['new']}"]
                if nu:
                    parts.append(f"new_id={nu.get('id')} new_auth={nu.get('auth')}")
                if ou:
                    parts.append(f"old_id={ou.get('id')} old_auth={ou.get('auth')}")
                print("  ".join(parts))
        print()

    safe_count = len(counts.get("SAFE_RENAME", []))
    auth_count = len(counts.get("AUTH_FIX_RENAME", []))
    total_fixable = safe_count + auth_count
    print(f"  >>> {total_fixable} casos restaurables con --fix")
    print(f"  >>> {len(counts.get('GONE', []))} requieren --recreate-gone")
    print(f"  >>> {len(counts.get('CONFLICT', []))} requieren --conflicts-fix\n")


# ---------------------------------------------------------------------------
# Fix: rename back SAFE + AUTH_FIX pairs
# ---------------------------------------------------------------------------
async def run_fix(ms, pairs: list):
    print(f"\n  Renombrando usuarios de vuelta a su username original...\n")
    classified = await classify_all(ms, pairs)

    to_fix = [c for c in classified if c["status"] in ("SAFE_RENAME", "AUTH_FIX_RENAME")]

    if not to_fix:
        print("  No hay casos por restaurar.\n")
        return

    # Step 1: fix auth for AUTH_FIX_RENAME cases
    auth_fix = [c for c in to_fix if c["status"] == "AUTH_FIX_RENAME"]
    if auth_fix:
        print(f"  Paso 1: Fijando auth=manual en {len(auth_fix)} usuarios (auth=db)...")
        users = [c["new_user"] for c in auth_fix]
        ok, fail = await _update_batch_auth(ms, users)
        print(f"  [OK] auth=manual: {ok} | [FAIL]: {fail}\n")

    # Step 2: rename
    print(f"  Paso 2: Renombrando {len(to_fix)} usuarios...")
    ok = fail = 0
    restored = []
    for i, c in enumerate(to_fix):
        p = c["pair"]
        new_user = c["new_user"]
        user_id = new_user["id"]
        old_username = p["old"]
        result = await _update_user_username(ms, user_id, old_username)
        if result:
            ok += 1
            restored.append(p)
            if (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(to_fix)}] OK={ok} FAIL={fail}")
        else:
            fail += 1
            print(f"  [FAIL] id={user_id}: {new_user.get('username')} -> {old_username}")

    print(f"\n  Renombrados: {ok}")
    print(f"  Fallidos:    {fail}\n")

    # Step 3: verify
    if ok > 0:
        print("  Verificando...")
        verified = 0
        for p in restored:
            user = await _find_user_by_username(ms, p["old"])
            if user and user.get("auth") == "manual":
                verified += 1
            else:
                print(f"  [WARN] {p['old']}: no se pudo verificar o auth != manual")
        print(f"  Verificados: {verified}/{ok}\n")


# ---------------------------------------------------------------------------
# Recreate GONE accounts + re-enrol
# ---------------------------------------------------------------------------
async def run_recreate_gone(ms, pairs: list):
    classified = await classify_all(ms, pairs)
    gone = [c for c in classified if c["status"] == "GONE"]

    if not gone:
        print("  No hay cuentas eliminadas por recrear.\n")
        return

    print(f"\n  Recreando {len(gone)} cuentas eliminadas...\n")

    for i, c in enumerate(gone):
        p = c["pair"]
        username = p["old"]
        email = p["email"] or f"{p['new']}{settings.INSTITUTIONAL_EMAIL_DOMAIN}"
        firstname = p["firstname"]
        lastname = p["lastname"]
        courses = p["courses"]
        cedula = p["cedula"]

        print(f"  [{i+1}/{len(gone)}] Creando {username} (email={email})...")
        created = await _create_user(ms, username, email, firstname, lastname)
        if not created:
            print(f"    [FAIL] No se pudo crear {username}")
            continue
        user_id = created.get("id")
        print(f"    [OK] Creado id={user_id} username={username}")

        # Re-enrol
        if courses and user_id:
            enrolled = 0
            for shortname in courses:
                course_id = await _get_course_id(ms, shortname)
                if course_id and await _enrol_user(ms, user_id, course_id):
                    enrolled += 1
                else:
                    print(f"    [WARN] No se pudo matricular en {shortname}")
            print(f"    Matriculas: {enrolled}/{len(courses)}")
        print()

    print(f"  Recreacion completada.\n")


# ---------------------------------------------------------------------------
# Conflicts fix: keep original username account, auth manual + re-enrol
# ---------------------------------------------------------------------------
async def run_conflicts_fix(ms, pairs: list):
    classified = await classify_all(ms, pairs)
    conflicts = [c for c in classified if c["status"] == "CONFLICT"]

    if not conflicts:
        print("  No hay conflictos por resolver.\n")
        return

    print(f"\n  Resolviendo {len(conflicts)} conflictos (conservando username original)...\n")

    for i, c in enumerate(conflicts):
        p = c["pair"]
        old_user = c.get("old_user")
        new_user = c.get("new_user")
        if not old_user or not new_user:
            continue

        print(f"  [{i+1}/{len(conflicts)}] {p['old']} (original) vs {p['new']} (email-prefix)")
        print(f"    old: id={old_user.get('id')} auth={old_user.get('auth')}")
        print(f"    new: id={new_user.get('id')} auth={new_user.get('auth')}")

        # Fix auth on original
        if old_user.get("auth") != "manual":
            print(f"    Fijando auth=manual en {p['old']} (id={old_user['id']})...")
            if await _update_user_auth(ms, old_user["id"]):
                print(f"    [OK] auth=manual")
            else:
                print(f"    [FAIL] No se pudo fijar auth")
                continue

        # Re-enrol original account from courses data
        courses = p["courses"]
        if courses and old_user.get("id"):
            print(f"    Re-matriculando en {len(courses)} cursos...")
            enrolled = 0
            for shortname in courses:
                course_id = await _get_course_id(ms, shortname)
                if course_id and await _enrol_user(ms, old_user["id"], course_id):
                    enrolled += 1
                else:
                    print(f"    [WARN] No se pudo matricular en {shortname}")
            print(f"    Matriculas: {enrolled}/{len(courses)}")
        print()

    print(f"  Conflictos resueltos.\n")


# ---------------------------------------------------------------------------
# CSV notification
# ---------------------------------------------------------------------------
def generate_csv(pairs: list, output_path: str):
    rows = []
    for p in pairs:
        rows.append({
            "email": p.get("email", ""),
            "username_original": p["old"],
            "username_erroneo": p["new"],
            "firstname": p.get("firstname", ""),
            "lastname": p.get("lastname", ""),
        })
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "email", "username_original", "username_erroneo", "firstname", "lastname",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print(f"  CSV generado: {output_path} ({len(rows)} docentes)\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    parser = argparse.ArgumentParser(
        description="Restaura usernames originales de Moodle renombrados por el bug del ETL"
    )
    parser.add_argument("--modalidad", default="DISTANCIA",
                        help="Modalidad (DISTANCIA/PRESENCIAL)")
    parser.add_argument("--audit", action="store_true",
                        help="Clasificar los 128 pares (solo lectura)")
    parser.add_argument("--fix", action="store_true",
                        help="Aplicar renombramiento de vuelta (safe + auth-fix)")
    parser.add_argument("--recreate-gone", action="store_true",
                        help="Recrear las 3 cuentas eliminadas + re-matricular")
    parser.add_argument("--conflicts-fix", action="store_true",
                        help="Resolver conflictos conservando username original")
    parser.add_argument("--csv", type=str, default=None,
                        help="Generar CSV de notificacion en la ruta especificada")
    parser.add_argument("--all", action="store_true",
                        help="Ejecutar --fix + --conflicts-fix + --recreate-gone")
    args = parser.parse_args()

    print(f"\n=== restore_original_usernames | modalidad={args.modalidad} ===\n")

    pairs = load_pairs()
    print(f"  {len(pairs)} pares cargados desde {DATA_FILE}")

    ms = get_moodle_service(args.modalidad)

    try:
        if args.audit:
            await run_audit(ms, pairs)
            return

        if args.all:
            await run_fix(ms, pairs)
            await run_conflicts_fix(ms, pairs)
            await run_recreate_gone(ms, pairs)
            if args.csv:
                generate_csv(pairs, args.csv)
            return

        if args.fix:
            await run_fix(ms, pairs)

        if args.conflicts_fix:
            await run_conflicts_fix(ms, pairs)

        if args.recreate_gone:
            await run_recreate_gone(ms, pairs)

        if args.csv:
            generate_csv(pairs, args.csv)

        if not (args.fix or args.conflicts_fix or args.recreate_gone or args.csv):
            await run_audit(ms, pairs)
            print("  Usa --fix, --conflicts-fix, --recreate-gone, o --all para aplicar cambios.\n")

    finally:
        await ms.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
