import type { FreshContext } from "@fresh/core";
import { tokenHaExpirado } from "./autenticacion.ts";

function getCookie(name: string, headers: Headers | null): string | null {
  const cookie = headers?.get("cookie");
  if (!cookie) return null;
  for (const part of cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

function tokenValido(headers: Headers | null): boolean {
  const token = getCookie("auth_token", headers);
  if (!token) return false;
  return !tokenHaExpirado(token);
}

export function requerirAutenticacion() {
  return {
    GET(ctx: FreshContext) {
      if (!tokenValido(ctx.req.headers)) {
        return ctx.redirect("/ingreso");
      }
      return { data: {} };
    },
  };
}

export function redirigirSiAutenticado() {
  return {
    GET(ctx: FreshContext) {
      if (tokenValido(ctx.req.headers)) {
        return ctx.redirect("/panel");
      }
      return { data: {} };
    },
  };
}
