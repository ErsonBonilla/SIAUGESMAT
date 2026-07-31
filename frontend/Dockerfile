# frontend/Dockerfile
FROM denoland/deno:2.5.6

WORKDIR /app

# Capa de dependencias del framework: solo se invalida si cambian
# deno.json / deno.lock / main.ts / dev.ts / fresh.config.ts.
COPY deno.json deno.lock main.ts dev.ts fresh.config.ts ./

# Cachear dependencias del framework (reintentos ante fallos transitorios de red)
RUN sh -c 'for i in 1 2 3 4 5; do deno cache main.ts dev.ts fresh.config.ts && exit 0; echo "intento $i fallido, reintentando"; sleep 5; done; exit 1'

# Copiar el resto de la aplicación
COPY . .

# Build Fresh (Tailwind compilado vía plugin).
# --mount=type=cache persiste las descargas de la app entre builds (BuildKit),
# y el loop reintenta ante fallos transitorios (DNS/Network unreachable).
RUN --mount=type=cache,target=/deno-dir \
    sh -c 'for i in 1 2 3 4 5; do deno task build && exit 0; echo "intento $i fallido, reintentando"; sleep 5; done; exit 1'

# Bake de dependencias de runtime (p. ej. fresh/internal) en la imagen
# para que `deno serve` no descargue en caliente al arrancar.
RUN sh -c 'for i in 1 2 3 4 5; do deno cache _fresh/server.js && exit 0; echo "intento $i fallido, reintentando"; sleep 5; done; exit 1'

EXPOSE 3000

ENV PORT=3000
ENV BACKEND_URL=http://backend:8000/api/v1
ENV DOCKER_ENV=1

CMD ["deno", "task", "preview"]
