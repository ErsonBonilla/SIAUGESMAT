#!/usr/bin/env -S deno run -A --watch=static/,routes/
import { Builder } from "@fresh/core/dev";
import { tailwind } from "@fresh/plugin-tailwind";
import config from "./fresh.config.ts";

const builder = new Builder({ root: "." });
tailwind(builder);

if (Deno.args.includes("build")) {
  await builder.build(config);
} else {
  const port = Number(Deno.env.get("PORT")) || 3000;
  await builder.listen(() => import("./main.ts"), { port });
}
