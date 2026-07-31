// services/api/core.ts
import { getToken, removeToken } from "../../utils/auth.ts";

export const BASE_URL = typeof Deno !== "undefined"
  ? Deno.env.get("BACKEND_URL")
  : "/api/v1";

export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status === 401) {
      removeToken();
      try {
        await fetch(`${BASE_URL}/auth/logout`, { method: "POST" });
      } catch {
        // best-effort: el estado local ya se limpió
      }
      if (typeof window !== "undefined") window.location.href = "/login";
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
