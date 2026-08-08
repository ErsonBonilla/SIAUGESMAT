"""Restablece la contraseña de un usuario y opcionalmente verifica con un
login real interactivo (form POST a /login/index.php).

Uso:
  # Solo reset de contraseña sin verificación de login
  python tools/reset_moodle_password.py --modalidad DISTANCIA \
    --username etiqueg --password '@Tique#997'

  # Con verificación de login real (requiere manejo de logintoken CSRF)
  python tools/reset_moodle_password.py --modalidad DISTANCIA \
    --username etiqueg --password '@Tique#997' --verify-login
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.core.config import settings
from app.services.moodle_factory import get_moodle_service

_LOGINTOKEN_RE = re.compile(r'<input\s+type="hidden"\s+name="logintoken"\s+value="([^"]+)"')


def _print_safe_error(msg: str, password: str) -> str:
    return msg.replace(password, "********")


# ---------------------------------------------------------------------------
# Moodle API helpers (read + update)
# ---------------------------------------------------------------------------
async def _get_user(ms, username: str) -> dict | None:
    """Consulta usuario por username y muestra estado relevante."""
    try:
        users = await ms.get_users("username", [username])
    except Exception as e:
        print(f"  [ERROR] Buscando usuario '{username}': {e}")
        return None
    if not users:
        print(f"  [INFO] Usuario '{username}' no encontrado en Moodle.")
        return None
    u = users[0]
    prefs = {p["name"]: p["value"] for p in u.get("preferences", [])}
    print(
        f"  Usuario encontrado: id={u['id']} username={u['username']} "
        f"auth={u.get('auth', '?')} suspended={u.get('suspended', '?')} "
        f"confirmed={u.get('confirmed', '?')}"
    )
    failed = prefs.get("login_failed_count_since_success", "0")
    locked = prefs.get("login_lockout")
    print(f"  login_failed_count_since_success = {failed}")
    if locked:
        print(f"  login_lockout = {locked} (LOCKED)")
    return u


async def _fix_auth(ms, user_id: int) -> bool:
    """Fija auth=manual si no lo es."""
    try:
        await ms._request(
            "core_user_update_users",
            params={
                "users[0][id]": user_id,
                "users[0][auth]": "manual",
            },
            use_post=True,
            timeout=30.0,
        )
        return True
    except Exception as e:
        print(f"  [ERROR] Fijando auth=manual: {e}")
        return False


async def _reset_password(ms, user_id: int, password: str) -> bool:
    """Restablece la contraseña via core_user_update_users."""
    try:
        await ms._request(
            "core_user_update_users",
            params={
                "users[0][id]": user_id,
                "users[0][password]": password,
            },
            use_post=True,
            timeout=30.0,
        )
        return True
    except Exception as e:
        msg = _print_safe_error(str(e), password)
        print(f"  [ERROR] Reset de contraseña: {msg}")
        return False


# ---------------------------------------------------------------------------
# Login verification (POST real a /login/index.php)
# ---------------------------------------------------------------------------
async def _verify_login(base_url: str, username: str, password: str) -> bool:
    """
    Realiza un POST de login interactivo contra Moodle.
    Retorna True si el login fue exitoso.

    Moodle 3.9+ puede redirigir a login?testsession=ID incluso tras login
    exitoso; se sigue la cadena de redirecciones acumulando cookies.
    """
    login_url = f"{base_url.rstrip('/')}/login/index.php"
    TIMEOUT = 30.0

    async with httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT) as client:
        # 1. GET login page → cookies + logintoken
        try:
            r = await client.get(login_url)
        except Exception as e:
            print(f"  [ERROR] GET login page: {e}")
            return False
        jar = httpx.Cookies()
        jar.update(r.cookies)
        m = _LOGINTOKEN_RE.search(r.text)
        if not m:
            print(f"  [WARN] No se encontró logintoken. status={r.status_code}")
            return False
        token = m.group(1)

        # 2. POST credentials
        try:
            r2 = await client.post(
                login_url,
                data={
                    "username": username,
                    "password": password,
                    "logintoken": token,
                },
                cookies=jar,
            )
        except Exception as e:
            print(f"  [ERROR] POST login: {e}")
            return False

        # 3. Pipeline: accumulate cookies, follow redirect chain
        jar.update(r2.cookies)
        location = r2.headers.get("location", "")
        max_hops = 8
        last_status = r2.status_code
        last_body = ""
        final_url = login_url

        for hop in range(max_hops):
            if location:
                final_url = location
                is_home = "/login/" not in location
                if is_home:
                    print(f"  Login OK: redirect → {location}")
                    return True
                # testsession or other login-page redirect
                try:
                    r_next = await client.get(location, cookies=jar)
                except Exception as e:
                    print(f"  [ERROR] Hop {hop}: {e}")
                    return False
                jar.update(r_next.cookies)
                location = r_next.headers.get("location", "")
                last_status = r_next.status_code
                last_body = r_next.text
                if not location:
                    break
            else:
                last_body = r2.text
                break

        # 4. Final page inspection
        body_lower = last_body.lower()
        if "/login/" not in final_url or "siteadmin" in body_lower or "dashboard" in body_lower:
            print(f"  Login OK (no login page at final URL: {final_url})")
            return True

        # 5. Parse error message
        error = re.search(
            r'(?:loginerrormessage|alert-danger|class="error"[^>]*>)\s*([^<]{10,200})',
            body_lower,
            re.IGNORECASE,
        )
        msg = error.group(1).strip()[:200] if error else ""
        if msg:
            print(f"  Login fallido: {msg}")
        else:
            print(f"  Login fallido. status={last_status} url={final_url}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def _main():
    p = argparse.ArgumentParser(description="Restablece contraseña de usuario Moodle.")
    p.add_argument("--modalidad", required=True, help="PRESENCIAL o DISTANCIA")
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument(
        "--verify-login", action="store_true", help="Hacer POST real de login después del reset"
    )
    args = p.parse_args()

    password = args.password
    username = args.username
    config = settings.get_moodle_config(args.modalidad)
    base_url = config["url"]
    version = config.get("version", "3.9")

    print(
        f"\n=== reset_moodle_password | modalidad={args.modalidad} "
        f"| version={version} | base={base_url} ===\n"
    )

    ms = get_moodle_service(args.modalidad)

    # 1. Leer estado previo
    print("--- Estado previo ---")
    user = await _get_user(ms, username)
    if not user:
        print("No se puede continuar sin usuario. Abortando.")
        raise SystemExit(1)
    user_id = int(user["id"])
    current_auth = user.get("auth", "")
    if current_auth and current_auth != "manual":
        print(f"\n  [ACTION] auth={current_auth}, fijando manual...")
        if not await _fix_auth(ms, user_id):
            print("  No se pudo fijar auth=manual. Continuando con el reset.")
    elif not current_auth:
        print("\n  [WARN] auth no reportado por la API. Se intentará reset sin fix.")

    # 2. Reset password
    print("\n--- Reset de contraseña ---")
    if await _reset_password(ms, user_id, password):
        print("  Contraseña restablecida exitosamente.")
    else:
        print("  El reset falló. Revisa la política de contraseñas del sitio.")
        raise SystemExit(1)

    # 3. Releer y mostrar estado
    print("\n--- Estado posterior ---")
    user = await _get_user(ms, username)

    # 4. Verificar login interactivo (opcional)
    if args.verify_login:
        print("\n--- Verificación de login interactivo ---")
        ok = await _verify_login(base_url, username, password)
        if ok:
            print("  Verificación: EXITOSA. El usuario puede entrar con la contraseña.")
            print("\n--- Contador post-login ---")
            await _get_user(ms, username)
        else:
            print("  Verificación: FALLIDA. El login interactivo no tuvo éxito.")

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(_main())
