// services/api/nucleo.ts
import { leerTokenCsrf } from "../../utils/csrf.ts";

export const BASE_URL = typeof Deno !== "undefined"
  ? (Deno.env.get("BACKEND_URL") || "http://localhost:8000/api/v1")
  : "/api/v1";

export function cabecerasAuth(): Record<string, string> {
  const csrf = leerTokenCsrf();
  return csrf ? { "X-CSRF-Token": csrf } : {};
}

export async function manejarRespuesta<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status === 401) {
      try {
        await fetch(`${BASE_URL}/auth/logout`, { method: "POST" });
      } catch {
        // best-effort: la cookie de sesión se invalidará en el servidor.
      }
      if (typeof window !== "undefined") window.location.href = "/ingreso";
      throw new Error("Sesión expirada. Vuelva a iniciar sesión.");
    }
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail || body?.message ||
        `Error del servidor (${response.status})`,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}
