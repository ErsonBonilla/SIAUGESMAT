import type { FreshContext } from "@fresh/core";

function getCookie(name: string, req: Request): string | null {
  const cookie = req.headers.get("cookie");
  if (!cookie) return null;
  for (const part of cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return rest.join("=");
  }
  return null;
}

function tokenPresent(req: Request): boolean {
  return getCookie("auth_token", req) !== null;
}

export function requireAuth() {
  return {
    GET(req: Request, ctx: FreshContext) {
      if (!tokenPresent(req)) {
        return new Response("", {
          status: 302,
          headers: { Location: "/login" },
        });
      }
    },
  };
}

export function redirectIfAuth() {
  return {
    GET(req: Request, ctx: FreshContext) {
      if (tokenPresent(req)) {
        return new Response("", {
          status: 302,
          headers: { Location: "/dashboard" },
        });
      }
    },
  };
}
