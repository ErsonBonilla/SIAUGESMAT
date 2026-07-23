// routes/index.tsx
import { Handlers } from "$fresh/server.ts";

/**
 * Página raíz que redirige según la presencia de un token de autenticación.
 *
 * - Si existe la cookie "auth_token", redirige al dashboard.
 * - Si no existe, redirige a la página de inicio de sesión.
 */
export const handler: Handlers = {
  GET(req) {
    const cookies = req.headers.get("cookie") || "";
    const token = cookies.split(";").some((c) => c.trim().startsWith("auth_token="));

    if (token) {
      // Token presente → redirigir al panel principal
      return new Response("", {
        status: 302,
        headers: { Location: "/dashboard" },
      });
    }

    // Sin token → redirigir al login
    return new Response("", {
      status: 302,
      headers: { Location: "/login" },
    });
  },
};