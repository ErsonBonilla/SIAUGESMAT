import { assertEquals } from "@std/assert";
import { redirectIfAuth, requireAuth } from "../../utils/auth-guard.ts";

function makeCtx(cookie?: string) {
  const headers = new Headers();
  if (cookie) headers.set("cookie", cookie);
  const ctx = {
    req: { headers },
    next: async () => undefined,
  } as any;
  ctx.redirect = (path: string, status = 302) =>
    new Response("", { status, headers: { Location: path } });
  return ctx;
}

Deno.test("requireAuth - redirects to /login when no auth cookie", async () => {
  const handlers = requireAuth();
  const res = await handlers.GET!(makeCtx());
  assertEquals((res as Response).status, 302);
  assertEquals((res as Response).headers.get("Location"), "/login");
});

Deno.test("requireAuth - continues when auth cookie present", async () => {
  const handlers = requireAuth();
  const res = await handlers.GET!(makeCtx("auth_token=abc"));
  assertEquals(res, { data: {} });
});

Deno.test("redirectIfAuth - redirects to /dashboard when auth cookie present", async () => {
  const handlers = redirectIfAuth();
  const res = await handlers.GET!(makeCtx("auth_token=abc"));
  assertEquals((res as Response).status, 302);
  assertEquals((res as Response).headers.get("Location"), "/dashboard");
});

Deno.test("redirectIfAuth - continues when no auth cookie", async () => {
  const handlers = redirectIfAuth();
  const res = await handlers.GET!(makeCtx());
  assertEquals(res, { data: {} });
});
