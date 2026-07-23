// routes/historico.tsx — redirige a /operaciones/historico
import { Handlers } from "$fresh/server.ts";

export const handler: Handlers = {
  GET(_req) {
    return new Response("", {
      status: 302,
      headers: { Location: "/operaciones/historico" },
    });
  },
};
