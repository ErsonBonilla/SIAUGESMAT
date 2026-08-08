// utils/auth.ts

/**
 * Clave única utilizada para almacenar el token JWT tanto en localStorage
 * como en las cookies de sesión.
 */
const TOKEN_KEY = "auth_token";

// ---------------------------------------------------------------------------
// Tipos internos
// ---------------------------------------------------------------------------

/** Estructura esperada del payload del JWT (claims). */
export interface TokenPayload {
  exp?: number;
  username?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Gestión del token en localStorage (cliente)
// ---------------------------------------------------------------------------

/**
 * Obtiene el token JWT desde localStorage.
 * Retorna null si localStorage no está disponible (entorno de servidor)
 * o si el token no existe.
 */
export function getToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Guarda el token JWT en localStorage.
 * En entornos donde localStorage no existe (servidor), la función
 * simplemente no hace nada.
 */
export function setToken(token: string): void {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

/**
 * Elimina el token JWT de localStorage.
 */
export function removeToken(): void {
  if (typeof localStorage !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}

// ---------------------------------------------------------------------------
// Utilidades de validación y extracción de datos del token
// ---------------------------------------------------------------------------

/**
 * Decodifica el payload (segmento 2) de un JWT en base64url.
 *
 * El JWT producido por python-jose usa base64url (caracteres `-`/`_`) y omite
 * el padding `=`, por lo que `atob` directo falla. Se normaliza a base64
 * estándar y se decodifican los bytes como UTF-8 (los payloads pueden
 * contener caracteres no ASCII, p. ej. nombres con acentos).
 */
function base64UrlDecode(segment: string): string {
  const b64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = b64.padEnd(Math.ceil(b64.length / 4) * 4, "=");
  const bytes = atob(padded).split("").map((c) => c.charCodeAt(0));
  return new TextDecoder().decode(new Uint8Array(bytes));
}

/**
 * Comprueba si el token almacenado en localStorage es válido (no ha expirado).
 *
 * Realiza una decodificación básica del payload sin verificar la firma
 * (la firma ya fue validada por el backend). Si el token no contiene
 * el campo `exp`, se considera válido indefinidamente.
 *
 * @returns `true` si el token existe y no ha expirado, `false` en caso contrario.
 */
export function isTokenValid(): boolean {
  const token = getToken();
  if (!token) return false;

  try {
    const payload: TokenPayload = JSON.parse(
      base64UrlDecode(token.split(".")[1]),
    );
    if (!payload.exp) return true; // sin expiración se asume válido
    return Date.now() < payload.exp * 1000;
  } catch {
    return false;
  }
}

/**
 * Decodifica el payload del token (sin verificar la firma).
 *
 * @returns Un objeto con los claims del token, o `null` si el token
 *          no existe o no se puede decodificar.
 */
export function getTokenPayload(): TokenPayload | null {
  const token = getToken();
  if (!token) return null;

  try {
    return JSON.parse(base64UrlDecode(token.split(".")[1]));
  } catch {
    return null;
  }
}

/**
 * Obtiene el nombre de usuario contenido en el token.
 *
 * @returns El valor del claim `username`, o `null` si no está disponible.
 */
export function getUsername(): string | null {
  const payload = getTokenPayload();
  return payload?.username ?? null;
}
