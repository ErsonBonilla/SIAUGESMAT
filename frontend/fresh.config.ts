import type { FreshConfig } from "@fresh/core";

const config: FreshConfig = {
  basePath: "",
  mode: Deno.env.get("DENO_ENV") === "development"
    ? "development"
    : "production",
};

export default config;
