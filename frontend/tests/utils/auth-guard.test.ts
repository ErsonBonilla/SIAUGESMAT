import { assertEquals } from "@std/assert";
import { redirectIfAuth, requireAuth } from "../../utils/auth-guard.ts";

function makeReq(cookie?: string): Request {
  const headers = new Headers();
  if (cookie) headers.set("cookie", cookie);
  return new Request("http://localhost", { headers });
}

Deno.test("requireAuth - redirects to /login when no auth cookie", async () => {
  const handlers = requireAuth();
  const res = await handlers.GET!(makeReq(), {} as any);
  assertEquals((res as Response).status, 302);
  assertEquals((res as Response).headers.get("Location"), "/login");
});

Deno.test("requireAuth - continues when auth cookie present", async () => {
  const handlers = requireAuth();
  const res = await handlers.GET!(makeReq("auth_token=abc"), {} as any);
  assertEquals(res, undefined);
});

Deno.test("redirectIfAuth - redirects to /dashboard when auth cookie present", async () => {
  const handlers = redirectIfAuth();
  const res = await handlers.GET!(makeReq("auth_token=abc"), {} as any);
  assertEquals((res as Response).status, 302);
  assertEquals((res as Response).headers.get("Location"), "/dashboard");
});

Deno.test("redirectIfAuth - continues when no auth cookie", async () => {
  const handlers = redirectIfAuth();
  const res = await handlers.GET!(makeReq(), {} as any);
  assertEquals(res, undefined);
});
