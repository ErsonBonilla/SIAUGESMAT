// routes/index.tsx
import type { FreshContext } from "@fresh/core";

/**
 * Página raíz que redirige según la presencia de un token de autenticación.
 *
 * - Si existe la cookie "auth_token", redirige al dashboard.
 * - Si no existe, redirige a la página de inicio de sesión.
 */
export const handler = {
  GET(req: Request, _ctx: FreshContext) {
    const cookies = req.headers.get("cookie") || "";
    const token = cookies.split(";").some((c) =>
      c.trim().startsWith("auth_token=")
    );

    if (token) {
      return new Response("", {
        status: 302,
        headers: { Location: "/dashboard" },
      });
    }

    return new Response("", {
      status: 302,
      headers: { Location: "/login" },
    });
  },
};
