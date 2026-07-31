// services/api/auth.ts
import { authHeaders, BASE_URL, handleResponse } from "./core.ts";
import type { UserProfile } from "./types.ts";

export async function login(
  username: string,
  password: string,
  modalidad: string,
) {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, modalidad }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || body?.message || "Credenciales inválidas");
  }
  return response.json() as Promise<
    {
      access_token: string;
      user_id: number;
      username: string;
      modalidad: string;
    }
  >;
}

export async function getMyProfile(): Promise<UserProfile> {
  const response = await fetch(`${BASE_URL}/auth/me`, {
    headers: { ...authHeaders() },
  });
  return handleResponse<UserProfile>(response);
}

export async function logout(): Promise<void> {
  try {
    await fetch(`${BASE_URL}/auth/logout`, { method: "POST" });
  } catch {
    // El logout es best-effort; si falla, el cliente limpia el estado local.
  }
}
