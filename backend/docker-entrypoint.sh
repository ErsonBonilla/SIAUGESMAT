#!/bin/sh
# Entrypoint de la imagen backend de SIAUGESMAT.
#
# Si RUN_MIGRATIONS=1, aplica las migraciones de Alembic antes de arrancar
# el proceso principal (backend/worker/beat pueden arrancar seguros sobre
# un esquema ya migrado). En el despliegue Docker las migraciones las
# ejecuta el servicio one-shot "migrate"; este guard es una red de seguridad
# para quien ejecute la imagen directamente.
set -e

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  echo "[entrypoint] Aplicando migraciones Alembic (alembic upgrade head)..."
  alembic upgrade head
  echo "[entrypoint] Migraciones aplicadas correctamente."
fi

exec "$@"