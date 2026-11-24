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
        await fetch(`${BASE_URL}/auth/logout`, {
          method: "POST",
          headers: { ...cabecerasAuth() },
        });
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

export function construirQuery(
  params: Record<string, string | number | undefined>,
): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") {
      sp.set(k, String(v));
    }
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

export async function peticionJson<T>(
  ruta: string,
  opciones: {
    method?: string;
    params?: Record<string, string | number | undefined>;
    json?: unknown;
    form?: FormData;
  } = {},
): Promise<T> {
  const qs = opciones.params ? construirQuery(opciones.params) : "";
  const headers: Record<string, string> = { ...cabecerasAuth() };
  let body: BodyInit | undefined;
  if (opciones.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opciones.json);
  } else if (opciones.form) {
    body = opciones.form;
  }
  const init: RequestInit = {
    headers,
    ...(opciones.method ? { method: opciones.method } : {}),
    ...(body !== undefined ? { body } : {}),
  };
  const response = await fetch(`${BASE_URL}${ruta}${qs}`, init);
  return manejarRespuesta<T>(response);
}
