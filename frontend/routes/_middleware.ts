// routes/_middleware.ts
import type { FreshContext } from "@fresh/core";

interface AppState {
  theme?: string;
}

/**
 * Middleware global que lee la cookie `theme` y la pasa al estado
 * para que _app.tsx pueda renderizar el tema correcto en SSR.
 */
export async function handler(req: Request, ctx: FreshContext<AppState>) {
  const cookies = req.headers.get("cookie") || "";
  const themeMatch = cookies.split(";").find((c) =>
    c.trim().startsWith("theme=")
  );
  ctx.state.theme = themeMatch ? themeMatch.split("=")[1].trim() : "dark";
  return await ctx.next();
}
