# backend/Dockerfile
FROM python:3.12.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias del sistema solo para Chromium headless (kaleido/Plotly PNG)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
        libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxrandr2 libgbm1 libasound2 \
        libpango-1.0-0 libcairo2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root para seguridad
RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --gid 1001 app

WORKDIR /app

# Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente y migraciones
COPY ./app ./app
COPY ./alembic.ini ./alembic.ini
COPY ./alembic ./alembic

# Crear directorios para uploads/reports con permisos correctos
RUN mkdir -p /app/uploads /app/reports && \
    chown -R app:app /app

EXPOSE 8000

USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
