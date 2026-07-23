#!/usr/bin/env -S deno run -A --watch=static/,routes/
import dev from "$fresh/dev.ts";

// Iniciar el servidor de desarrollo con recarga automática
await dev(import.meta.url, "./main.ts");