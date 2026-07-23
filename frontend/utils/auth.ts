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
interface TokenPayload {
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
// Gestión del token mediante cookies (accesible desde el servidor)
// ---------------------------------------------------------------------------

/**
 * Crea una cookie con el token JWT para que los handlers del servidor
 * puedan leerla y permitir el acceso a rutas protegidas.
 *
 * La cookie expira en 1 hora, es válida para toda la aplicación
 * (path=/) y utiliza SameSite=Lax para permitir peticiones desde
 * enlaces y formularios sin problemas de seguridad.
 */
export function setTokenCookie(token: string): void {
  if (typeof document === "undefined") return;
  const expires = new Date(Date.now() + 60 * 60 * 1000).toUTCString();
  document.cookie = `${TOKEN_KEY}=${token}; expires=${expires}; path=/; SameSite=Lax`;
}

/**
 * Elimina la cookie del token forzando su expiración inmediata.
 */
export function removeTokenCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${TOKEN_KEY}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax`;
}

// ---------------------------------------------------------------------------
// Utilidades de validación y extracción de datos del token
// ---------------------------------------------------------------------------

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
    const payload: TokenPayload = JSON.parse(atob(token.split(".")[1]));
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
    return JSON.parse(atob(token.split(".")[1]));
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