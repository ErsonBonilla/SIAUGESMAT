// routes/_middleware.ts
import type { FreshContext } from "@fresh/core";
import { normalizarTema } from "../utils/tema.ts";

interface AppState {
  theme?: string;
}

/**
 * Middleware global que lee la cookie `theme` y la pasa al estado
 * para que _app.tsx pueda renderizar el tema correcto en SSR.
 */
export async function handler(ctx: FreshContext<AppState>) {
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
