// utils/autenticacion.ts

// ---------------------------------------------------------------------------
// Tipos internos
// ---------------------------------------------------------------------------

/** Estructura esperada del payload del JWT (claims). */
export interface PayloadToken {
  exp?: number;
  username?: string;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Utilidades de validación del token
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
 * Comprueba si un token JWT (string crudo) ha expirado.
 *
 * Decodifica el payload sin verificar la firma (la firma ya fue validada por
 * el backend). Si el token no contiene el campo `exp` se considera no expirado.
 * Un token malformado se considera expirado.
 *
 * Se usa en el guard SSR de rutas (cookie `auth_token`) solo como control de
 * UX; la fuente de verdad de la autenticación sigue siendo el backend.
 */
export function tokenHaExpirado(token: string): boolean {
  try {
    const payload: PayloadToken = JSON.parse(
      base64UrlDecode(token.split(".")[1]),
    );
    if (!payload.exp) return false;
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true;
  }
}
