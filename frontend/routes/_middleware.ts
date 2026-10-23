// routes/_middleware.ts
import type { FreshContext } from "@fresh/core";
import { normalizarTema } from "../utils/tema.ts";

interface AppState {
  theme?: string;
}

const BACKEND_ORIGIN = (
  Deno.env.get("BACKEND_URL") || "http://localhost:8000/api/v1"
).replace(/\/api\/v1\/?$/, "");

/**
 * Middleware global:
 * 1. En desarrollo local (o acceso directo a :3000 sin Nginx), proxifica
 *    `/api/*` hacia el backend FastAPI preservando cookies y cabeceras CSRF.
 * 2. Lee la cookie `theme` y la pasa al estado para que `_app.tsx` renderice
 *    el tema correcto en SSR.
 */
export async function handler(ctx: FreshContext<AppState>) {
  const url = new URL(ctx.req.url);
  if (url.pathname.startsWith("/api/")) {
    const destino = `${BACKEND_ORIGIN}${url.pathname}${url.search}`;
    const headers = new Headers(ctx.req.headers);
    headers.delete("host");
    const upstream = await fetch(destino, {
      method: ctx.req.method,
      headers,
      body: ctx.req.method === "GET" || ctx.req.method === "HEAD"
        ? undefined
        : ctx.req.body,
      redirect: "manual",
    });
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: upstream.headers,
    });
  }

  const cookies = ctx.req.headers.get("cookie") || "";
  const themeMatch = cookies.split(";").find((c) =>
    c.trim().startsWith("theme=")
  );
  const crudo = themeMatch ? themeMatch.split("=")[1]?.trim() : "";
  ctx.state.theme = normalizarTema(crudo);

  const res = await ctx.next();
  if (res instanceof Response) {
    const ctype = res.headers.get("content-type") || "";
    if (ctype.includes("text/html")) {
      const headers = new Headers(res.headers);
      headers.set("Cache-Control", "no-store");
      return new Response(res.body, {
        status: res.status,
        statusText: res.statusText,
        headers,
      });
    }
  }
  return res;
}
