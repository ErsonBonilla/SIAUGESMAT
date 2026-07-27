# frontend/Dockerfile
FROM denoland/deno:2.5.6

WORKDIR /app

COPY . .

# Cachear dependencias (incluye tailwindcss via Fresh plugin)
RUN deno cache main.ts dev.ts fresh.config.ts

# Build Fresh (rutas, islas, manifest)
RUN deno task build

# Compilar Tailwind CSS manualmente (Fresh 1.7.2 no lo compila en build)
RUN deno run -A npm:tailwindcss@3.4.1 -- --config ./tailwind.config.js -i ./static/main.css -o ./_fresh/static/main.css --minify

# Copiar CSS personalizado y favicon a _fresh/static/
RUN cp static/styles.css _fresh/static/styles.css
RUN cp static/SIAUGESMAT.ico _fresh/static/SIAUGESMAT.ico

EXPOSE 3000

ENV BACKEND_URL=http://backend:8000/api/v1
ENV DOCKER_ENV=1

CMD ["deno", "task", "preview"]
