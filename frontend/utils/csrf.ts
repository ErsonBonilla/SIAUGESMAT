// utils/csrf.ts

/**
 * Lee el valor de la cookie `csrf_token` (no-HttpOnly) emitida por el backend
 * en el login. El frontend lo reenvía en la cabecera `X-CSRF-Token` en cada
 * mutación (esquema double-submit para protección CSRF).
 */
export function leerTokenCsrf(): string {
  if (typeof document === "undefined") return "";
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return m ? m[1] : "";
}
