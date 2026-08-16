import type { FreshContext } from "@fresh/core";

function getCookie(name: string, headers: Headers | null): string | null {
  const cookie = headers?.get("cookie");
  if (!cookie) return null;
  for (const part of cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

function tokenPresent(headers: Headers | null): boolean {
  return getCookie("auth_token", headers) !== null;
}

export function requireAuth() {
  return {
    GET(ctx: FreshContext) {
      if (!tokenPresent(ctx.req.headers)) {
        return ctx.redirect("/ingreso");
      }
      return { data: {} };
    },
  };
}

export function redirectIfAuth() {
  return {
    GET(ctx: FreshContext) {
      if (tokenPresent(ctx.req.headers)) {
        return ctx.redirect("/panel");
      }
      return { data: {} };
    },
  };
}
