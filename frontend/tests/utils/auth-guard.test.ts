import { assertEquals } from "https://deno.land/std@0.224.0/assert/mod.ts";
import { requireAuth, redirectIfAuth } from "../../utils/auth-guard.ts";
import type { FreshContext } from "$fresh/server.ts";

function makeReq(cookie?: string): Request {
  const headers = new Headers();
  if (cookie) headers.set("cookie", cookie);
  return new Request("http://localhost", { headers });
}

const mockRender = () => new Response("rendered");

const lastCtx: FreshContext | null = null;

Deno.test("requireAuth - redirects to /login when no auth cookie", async () => {
  const handlers = requireAuth();
  const ctx = { render: mockRender } as unknown as FreshContext;
  const res = await handlers.GET!(makeReq(), ctx);
  assertEquals(res.status, 302);
  assertEquals(res.headers.get("Location"), "/login");
});

Deno.test("requireAuth - renders when auth cookie present", async () => {
  const handlers = requireAuth();
  const ctx = { render: mockRender } as unknown as FreshContext;
  const res = await handlers.GET!(makeReq("auth_token=abc"), ctx);
  assertEquals(res.status, 200);
});

Deno.test("redirectIfAuth - redirects to /dashboard when auth cookie present", async () => {
  const handlers = redirectIfAuth();
  const ctx = { render: mockRender } as unknown as FreshContext;
  const res = await handlers.GET!(makeReq("auth_token=abc"), ctx);
  assertEquals(res.status, 302);
  assertEquals(res.headers.get("Location"), "/dashboard");
});

Deno.test("redirectIfAuth - renders when no auth cookie", async () => {
  const handlers = redirectIfAuth();
  const ctx = { render: mockRender } as unknown as FreshContext;
  const res = await handlers.GET!(makeReq(), ctx);
  assertEquals(res.status, 200);
});
