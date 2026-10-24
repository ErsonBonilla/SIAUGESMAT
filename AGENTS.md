# AGENTS.md

Guía para agentes y desarrolladores que trabajan en SIAUGESMAT.

## Auditoría con Aider (DeepSeek)

Aider está configurado para auditar y editar el código con la API de DeepSeek
(`.aider.conf.yml` en la raíz). La clave se lee de `DEEPSEEK_API_KEY` en `.env`.

```bash
# Lanzar (el .exe global está bloqueado por App Control; usar uv con Python 3.12):
uv tool run --from aider-chat --python 3.12 aider

# Auditoría de SOLO LECTURA (preguntas/análisis sin editar):
uv tool run --from aider-chat --python 3.12 aider --chat-mode ask
#   ...o desde CLI en una sola llamada:
#   uv tool run --from aider-chat --python 3.12 aider --chat-mode ask -m "analiza X" --read <archivo>
```

- `deepseek-flash` (DeepSeek V4.1-Flash): 1M de contexto, salida hasta 384K,
  thinking mode nativo + function calling. Un solo modelo sirve para editar
  (diffs) y para auditar (razonar con `/ask`).
- Ajustes finos del modelo en `.aider.model.settings.yml` (fuerzan `diff` y
  `use_repo_map`, que aider no trae por defecto para este modelo).
- El thinking mode está activo por defecto; el esfuerzo se controla con
  `reasoning_effort` (`low`/`high`/`max`).
- Al arrancar se cargan como **solo-lectura**: `AGENTS.md` y los tests de
  contrato (`test_contrato_*.py`, `test_pureza_pipeline.py`), así el agente
  respeta los contratos externos sin poder romperlos.
- Los commits son manuales (`auto-commits: false`).

## Comandos de verificación

```bash
# Backend (backend/)
pip install -r requirements-dev.txt

ruff check app tests alembic        # lint
ruff format --check app tests alembic
pytest -q                            # suite completa (SQLite temporal, sin .env)

# Migraciones (backend/, requiere PostgreSQL)
alembic current
alembic upgrade head
alembic check                        # detecta drift entre modelos y la BD

# Frontend (frontend/)
deno task check                      # fmt --check + lint + deno check
deno test -A tests/
```

- La suite de tests **nunca** ejecuta las migraciones (usa `Base.metadata.create_all`
  sobre SQLite). La cadena `alembic upgrade head` se valida por separado (job
  `migraciones` del CI y `alembic check`).
- `backend/e2e/` requiere una API viva + Redis + Moodle real (o simulado) +
  `e2e/fixtures/MI_CARGA.xlsx`; no corre en CI.

## Contratos externos: NO renombrar

El código interno está en español, pero varios contratos con el exterior conservan
sus nombres ingleses **a propósito**. Son intencionales y están protegidos por tests
de contrato; no "arreglarlos" con un rename:

| Contrato externo | Ejemplo | Protegido por |
|---|---|---|
| Claves JSON de respuestas/solicitudes API | `batch_id`, `task_id`, `progress_pct` vía `Field(alias=...)` | `tests/test_contrato_wire.py` |
| URLs y query params | `/api/v1/analytics/executions/{id}/charts`, `?visibility=` | — |
| `name=` de tareas Celery | `app.workers.query_tasks.execute_query` | `tests/test_contrato_celery.py` |
| Nombres de tablas/columnas en SQL crudo | debe ser SIEMPRE español | `tests/test_contrato_sql_espanol.py` |
| Claves JSON internas de datos (`detalle`) | `action`, `phase`, `identifier` | — |
| Nombres de pkey/index de sistema | `operation_batches_pkey` (sin renombrar) | — |
| Hooks de override de librerías | `JsonFormatter.add_fields`, `logging.Filter.filter`, `__aenter__`/`__aexit__` | `tests/test_configuracion_logging.py` |

Regla de oro: se renombra lo **interno** (Python, ORM, tablas/columnas en migraciones,
SQL crudo), nunca un contrato **externo**. Tras cualquier rename, correr: `ruff`,
`pytest`, `deno task check`, `deno test`, `alembic check` y los tests de contrato.

## Trampas conocidas

- **FastAPI 0.141.1 traga kwargs desconocidos** en `FastAPI(...)` (van a `extra`
  sin error). Un typo como `lifespan=`→`ciclo_de_vida=` desactiva el startup en
  silencio. Protegido por `tests/test_contrato_lifespan.py`; los decoradores de
  ruta sí lanzan `TypeError` con kwargs desconocidos.
- **Renombres de módulos/paths**: si se renombra un módulo, actualizar también los
  prefijos de `tests/test_pureza_pipeline.py` (la lista debe apuntar a módulos
  reales, validado por `test_prefijos_prohibidos_resuelven_a_modulos_reales`).
- **SQL crudo**: preferir `Query.update(...)`/ORM sobre `text(...)`; si se usa SQL
  crudo, los nombres de tabla/columna deben venir del esquema español.
- **Servicios long-lived desde el tool `bash` (Windows)**: NO usar
  `Start-Process` para lanzar celery/uvicorn/mocks en segundo plano: el hijo
  hereda el pipe de stdout de opencode y la llamada `bash` queda `running` para
  siempre (bloquea la sesión). Usar `python e2e/levantar_stack_e2e.py`
  (lanzamiento con `DETACHED_PROCESS`, retorna al instante). Ejecutar el stack
  e2e simulado desde una sola sesión a la vez (BD `siaugesmat_e2e`, Redis
  índice 5 y puertos 8001/8800 son compartidos).