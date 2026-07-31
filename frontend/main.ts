/// <reference no-default-lib="true" />
/// <reference lib="dom" />
/// <reference lib="dom.iterable" />
/// <reference lib="dom.asynciterable" />
/// <reference lib="deno.ns" />

import { App, staticFiles } from "@fresh/core";
import config from "./fresh.config.ts";

const app = new App(config);
app.use(staticFiles());
app.fsRoutes();

export { app };

if (import.meta.main) {
  await app.listen();
}
