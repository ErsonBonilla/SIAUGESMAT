import { Handlers } from "$fresh/server.ts";

function tokenPresent(req: Request): boolean {
  return req.headers.get("cookie")?.includes("auth_token=") ?? false;
}

export function requireAuth(): Handlers {
  return {
    GET(req, ctx) {
      if (!tokenPresent(req)) {
        return new Response("", {
          status: 302,
          headers: { Location: "/login" },
        });
      }
      return ctx.render();
    },
  };
}

export function redirectIfAuth(): Handlers {
  return {
    GET(req, ctx) {
      if (tokenPresent(req)) {
        return new Response("", {
          status: 302,
          headers: { Location: "/dashboard" },
        });
      }
      return ctx.render();
    },
  };
}
