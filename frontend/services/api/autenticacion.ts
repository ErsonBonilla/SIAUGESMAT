// services/api/autenticacion.ts
import { BASE_URL, cabecerasAuth, manejarRespuesta } from "./nucleo.ts";
import type { PerfilUsuario } from "./tipos.ts";

export async function iniciarSesion(
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

export async function obtenerMiPerfil(): Promise<PerfilUsuario> {
  const response = await fetch(`${BASE_URL}/auth/me`, {
    headers: { ...cabecerasAuth() },
  });
  return manejarRespuesta<PerfilUsuario>(response);
}

export async function cerrarSesion(): Promise<void> {
  try {
    await fetch(`${BASE_URL}/auth/logout`, { method: "POST" });
  } catch {
    // El cerrarSesion es best-effort; si falla, el cliente limpia el estado local.
  }
}
