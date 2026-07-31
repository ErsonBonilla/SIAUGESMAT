# frontend/Dockerfile
FROM denoland/deno:2.5.6

WORKDIR /app

COPY . .

# Cachear dependencias
RUN deno cache main.ts dev.ts fresh.config.ts

# Build Fresh (Tailwind compilado vía plugin)
RUN deno task build

EXPOSE 3000

ENV PORT=3000
ENV BACKEND_URL=http://backend:8000/api/v1
ENV DOCKER_ENV=1

CMD ["deno", "task", "preview"]