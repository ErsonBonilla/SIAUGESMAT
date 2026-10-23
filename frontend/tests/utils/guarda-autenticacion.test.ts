import { assertEquals } from "@std/assert";
import {
  redirigirSiAutenticado,
  requerirAutenticacion,
} from "../../utils/guarda-autenticacion.ts";

function b64url(obj: unknown): string {
  return btoa(JSON.stringify(obj))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

function buildToken(exp?: number): string {
  const payload = exp ? { exp } : { username: "admin" };
  return `${b64url({ alg: "HS256", typ: "JWT" })}.${b64url(payload)}.firma`;
}

const EXP_FUTURO = Math.floor(Date.now() / 1000) + 3600;
const EXP_PASADO = Math.floor(Date.now() / 1000) - 3600;

function makeCtx(cookie?: string) {
  const headers = new Headers();
  if (cookie) headers.set("cookie", cookie);
  const ctx = {
    req: { headers },
    next: () => undefined,
  } as unknown as Parameters<
    ReturnType<typeof requerirAutenticacion>["GET"]
  >[0];
  ctx.redirect = (path: string, status = 302) =>
    new Response("", { status, headers: { Location: path } });
  return ctx;
}

Deno.test("requireAuth - redirects to /ingreso when no auth cookie", async () => {
  const handlers = requerirAutenticacion();
  const res = await handlers.GET!(makeCtx());
  assertEquals((res as Response).status, 302);
  assertEquals((res as Response).headers.get("Location"), "/ingreso");
});

Deno.test("requireAuth - continues when valid (non-expired) cookie", async () => {
  const handlers = requerirAutenticacion();
  const res = await handlers.GET!(
    makeCtx(`auth_token=${buildToken(EXP_FUTURO)}`),
  );
  assertEquals(res, { data: {} });
});

Deno.test("requireAuth - redirects when cookie is expired", async () => {
  const handlers = requerirAutenticacion();
  const res = await handlers.GET!(
    makeCtx(`auth_token=${buildToken(EXP_PASADO)}`),
  );
  assertEquals((res as Response).status, 302);
  assertEquals((res as Response).headers.get("Location"), "/ingreso");
});

Deno.test("requireAuth - redirects when cookie is malformed", async () => {
  const handlers = requerirAutenticacion();
  const res = await handlers.GET!(makeCtx("auth_token=abc"));
  assertEquals((res as Response).status, 302);
});

Deno.test("redirectIfAuth - redirects to /panel when valid cookie present", async () => {
  const handlers = redirigirSiAutenticado();
  const res = await handlers.GET!(
    makeCtx(`auth_token=${buildToken(EXP_FUTURO)}`),
  );
  assertEquals((res as Response).status, 302);
  assertEquals((res as Response).headers.get("Location"), "/panel");
});

Deno.test("redirectIfAuth - continues when no auth cookie", async () => {
  const handlers = redirigirSiAutenticado();
  const res = await handlers.GET!(makeCtx());
  assertEquals(res, { data: {} });
});

Deno.test("redirectIfAuth - continues when cookie is expired", async () => {
  const handlers = redirigirSiAutenticado();
  const res = await handlers.GET!(
    makeCtx(`auth_token=${buildToken(EXP_PASADO)}`),
  );
  assertEquals(res, { data: {} });
});
