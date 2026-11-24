# AGENTS.md

Guía arquitectónica y operativa para agentes de IA y desarrolladores que trabajan en **SIAUGESMAT**.

---

## 1. Arquitectura e invariantes de capas

### Backend (`backend/app/`)

- **`app/pipeline/` (Núcleo 100 % puro)**:
  - Contiene todas las transformaciones de negocio sin efectos secundarios (`nombres_cortos`, `indice_cursos`, `comparacion_cursos/`, `novedades`, `metricas`, `plan`, `progreso`, `categorias`, `usuarios`, `matriculaciones`).
  - **Prohibido** importar o usar: `app.db`, `app.repositories`, `app.core` (`settings`), `app.integrations`, `app.workers`, `app.api`, `app.schemas`, `sqlalchemy`, `httpx`, `pandas`, `openpyxl`, `celery`, `fastapi`.
  - Protegido por análisis AST en `tests/test_pureza_pipeline.py`.
- **`app/repositories/` (CRUD funcional)**:
  - Funciones puras de acceso a datos (sin clases de repositorio) que reciben `db: Session` como primer parámetro (`repositorio_ejecuciones`, `repositorio_registros`, `repositorio_consultas`, `repositorio_operaciones`).
  - Nunca instancian `SessionLocal()` por su cuenta.
- **Cadena de integración Moodle**:
  - `ClienteMoodle` (`services/cliente_moodle.py`: HTTP asíncrono + rate limit + reintentos) → `AdaptadorMoodle` (`services/adaptador_moodle.py`: diferencias Moodle 3.8/3.9 vs 4.x/5.x) → `ServicioMoodle` (`services/operaciones_moodle.py`) → `IntegracionMoodle` (`integrations/integracion_moodle.py`).
- **`app/workers/` (Celery síncrono)**:
  - Orquestador ETL por fases (`phases/fase1_consulta.py` a `fase4_personas.py`, `orquestador.py`, `tarea_item.py`) con contexto compartido (`ContextoFase`) y *checkpointing* en BD.
  - Los workers síncronos invocan corrutinas de Moodle exclusivamente a través del runner compartido `ejecutar_moodle_async` (`app/workers/utilidades.py`).

### Frontend (`frontend/`)

- **Islands Architecture** (Deno 2 + Fresh 2 + Preact + Signals):
  - `islands/`: componentes interactivos con estado (Signals), efectos y llamadas HTTP.
  - `components/`: componentes presentacionales puros (sin `fetch` ni efectos de red).
  - `services/api/`: cliente HTTP modularizado (`services/api.ts` actúa como *barrel*). Autenticación mediante cookie `HttpOnly` (`access_token`) + protección CSRF *double-submit* (cookie `csrf_token` enviada en la cabecera `X-CSRF-Token` en métodos mutadores).
  - `utils/`: señales globales (`senalTemaOscuro`, `senalPerfil`), constantes de marca/semáforo y utilidades puras.

---

## 2. Contratos externos: NO renombrar

El código interno está en **español**, pero varios contratos con el exterior conservan sus nombres en **inglés a propósito**. Son intencionales y están protegidos por tests de contrato; no "arreglarlos" con un rename:

| Contrato | Ejemplo | Protegido por |
|---|---|---|
| Claves JSON de respuestas/solicitudes API | `batch_id`, `task_id`, `progress_pct`, `execution_id` vía `Field(alias=...)` | `tests/test_contrato_wire.py` |
| URLs y query params de la API | `/api/v1/analytics/executions/{id}/charts`, `?visibility=show\|hide` | `tests/test_endpoints_api.py` |
| `name=` opacos de tareas Celery y `beat_schedule` | `app.workers.query_tasks.execute_query`, `app.workers.tasks.process_etl_file` | `tests/test_contrato_celery.py` |
| Nombres de tablas/columnas en SQL crudo | Deben usar **SIEMPRE** el esquema en español (`ejecuciones`, `lotes_operacion`, etc.) | `tests/test_contrato_sql_espanol.py` |
| Alineación ORM ↔ migraciones Alembic | Tablas, columnas e índices únicos renombrados a español sin drift | `tests/test_contrato_migraciones.py` |
| Registro del `lifespan` en `FastAPI(...)` | Kwarg `lifespan=` (no traducir a `ciclo_de_vida=`) | `tests/test_contrato_lifespan.py` |
| Hooks de override de librerías | `JsonFormatter.add_fields`, `logging.Filter.filter`, `__aenter__`/`__aexit__` | `tests/test_configuracion_logging.py` |
| Aislamiento del núcleo puro | Sin imports de I/O ni referencias a `settings`/`Session` en `app/pipeline/` | `tests/test_pureza_pipeline.py` |
| Claves JSON internas en `detalle` / `metricas` | `action`, `phase`, `identifier`, `courses_created` | `tests/test_contrato_wire.py` |
| Nombres de pkey de sistema heredados | `operation_batches_pkey` (sin renombrar en PG) | — |

**Regla de oro**: se renombra lo **interno** (símbolos Python, modelos ORM, tablas/columnas en migraciones y SQL crudo), nunca un contrato **externo**.

---

## 3. Convenciones de código, seguridad y Git

- **Idioma**: código interno, modelos ORM, docstrings, comentarios, mensajes de error de usuario y commits en **español**.
- **Python 3.12 y Ruff (`backend/ruff.toml`)**:
  - `line-length = 100`, anotaciones modernas (`X | None`, `list[...]`, `dict[...]`).
  - **Fechas con zona horaria (regla `DTZ`)**: usar siempre `datetime.now(UTC)`; nunca `datetime.utcnow()` ni datetimes *naive*.
  - **Seguridad estática (regla `S` / Bandit)**: activa en todo `app/`.
- **Detección de secretos (`.gitleaks.toml`)**:
  - Reglas personalizadas para tokens de Moodle (`moodle-ws-token`: 32 caracteres hexadecimales `[a-f0-9]{32}`).
  - En tests y ejemplos usar exclusivamente los placeholders permitidos (`token-de-prueba`, `tokendemo`, `tu-token-admin`, `tu-token-presencial`, `tu-token-distancia`, `clave-secreta-de-prueba-suficientemente-larga`, `genera-una-clave-segura-aqui`).
- **Git y Commits**:
  - Commits manuales (`auto-commits: false`), en español y siguiendo *Conventional Commits* (`feat(consultas): ...`, `fix(etl): ...`, `chore(infra): ...`, `docs: ...`).
  - Finales de línea `LF` forzados por `.gitattributes`.

---

## 4. Comandos de verificación (paridad local ↔ Lefthook ↔ CI)

```bash
# Backend (desde backend/; en Windows usar .venv\Scripts\<cmd>)
pip install -r requirements-dev.txt
ruff check app tests alembic              # lint (incluye Bandit y DTZ)
ruff format --check app tests alembic     # formato
vulture app --min-confidence 70           # detección de código muerto
pytest -q                                 # suite completa (SQLite temporal, sin .env)

# Migraciones (desde backend/, requiere PostgreSQL activo)
alembic current
alembic upgrade head
alembic check                             # detecta drift entre modelos ORM y la BD

# Frontend (desde frontend/)
deno task check                           # deno fmt --check + deno lint + deno check
deno test -A tests/                       # suite de tests frontend
deno task build                           # verificación de build de producción Fresh

# Infraestructura, Seguridad y Git Hooks (desde la raíz del repositorio)
docker compose --env-file .env.example -f docker-compose.yml config -q
docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.override.yml config -q
gitleaks git --redact --no-banner                        # escaneo de historial completo
gitleaks git --pre-commit --staged --redact --no-banner  # cambios en staging (pre-commit)
lefthook run pre-commit
lefthook run pre-push
```

- La suite `pytest` **nunca** ejecuta las migraciones por defecto (usa `Base.metadata.create_all` sobre una SQLite temporal). La cadena `alembic upgrade head` y `alembic check` se validan por separado (en local contra PostgreSQL y en el job `migraciones` del CI).
- `backend/e2e/` requiere API viva + Redis + Moodle real (o `moodle_simulado.py`) + fixtures `.xlsx`; no corre en CI.

---

## 5. Trampas conocidas

- **FastAPI 0.141.1 traga kwargs desconocidos** en `FastAPI(...)` (van a `extra` sin lanzar error). Un typo como `lifespan=` → `ciclo_de_vida=` desactiva el arranque (`inicializar_db` + `validar_critico`) en silencio. Protegido por `tests/test_contrato_lifespan.py`.
- **Renombres de módulos/paths**: si se renombra o mueve un módulo de `app/`, actualizar también `FORBIDDEN_IMPORT_PREFIXES` en `tests/test_pureza_pipeline.py` (`test_prefijos_prohibidos_resuelven_a_modulos_reales` fallará si algún prefijo deja de existir).
- **SQL crudo**: preferir `Query.update(...)`/ORM sobre `text(...)`; si se usa SQL crudo, los nombres de tabla y columna deben pertenecer al esquema en español (`tests/test_contrato_sql_espanol.py`).
- **Peligro con `SIAUGESMAT_TESTS_USE_DOTENV=1`**: el fixture `test_db` de `tests/conftest.py` ejecuta `Base.metadata.drop_all()` al finalizar cada test. **Jamás** activar `SIAUGESMAT_TESTS_USE_DOTENV=1` si `DATABASE_URL` en `.env` apunta a una base de datos con datos que no deban borrarse.
- **Fuente única de `.env`**: `app/core/config.py` carga el `.env` de la **raíz del repositorio** como fuente principal (igual que Docker Compose) y `backend/.env` únicamente como *override* local.
- **Servicios long-lived desde el tool `bash` (Windows)**: NO usar `Start-Process` para lanzar Celery/Uvicorn/mocks en segundo plano (el proceso hijo hereda el pipe de stdout y deja colgada la llamada `bash`). Usar `python e2e/levantar_stack_e2e.py` (usa `DETACHED_PROCESS` y retorna al instante). Ejecutar el stack e2e simulado desde una sola sesión a la vez (comparte BD `siaugesmat_e2e`, Redis índice 5 y puertos 8001/8800).
