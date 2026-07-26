// routes/upload.tsx — redirige a /cursos/crear
import { Handlers } from "$fresh/server.ts";

export const handler: Handlers = {
  GET(_req) {
    return new Response("", {
      status: 302,
      headers: { Location: "/cursos/crear" },
    });
  },
};
