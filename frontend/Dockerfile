# frontend/Dockerfile
FROM denoland/deno:2.5.6

WORKDIR /app

COPY . .
RUN deno task build

EXPOSE 3000

ENV BACKEND_URL=http://backend:8000/api/v1

CMD ["deno", "task", "preview"]
