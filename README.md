# 🎓 SIAUGESMAT

**Sistema de Integración y Automatización para la Gestión de Matrículas en Moodle**

Aplicación full-stack para la Universidad del Tolima que automatiza la carga masiva de cursos, usuarios y matriculaciones en **Tu Aula (Moodle 3.9)**. Procesa archivos Excel semestrales mediante el **Módulo de Novedades** (ETL de 5 fases) e incluye un **Módulo de Operaciones** para creación y eliminación masiva de entidades, consultas asíncronas, 14 reportes CSV con información detallada, 5 gráficos Plotly profesionales, dashboard de analítica y semáforos de estado en tiempo real.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| **Frontend** | Deno 2 + Fresh + Preact + Signals + Plotly.js |
| **Backend** | Python 3.12 + FastAPI + SQLAlchemy + Celery + Redis |
| **Base de datos** | PostgreSQL 17 |
| **Cola de tareas** | Redis 7 + Celery (+ Celery Beat para tareas periódicas) |
| **Integración Moodle** | API REST (versiones 3.8 a 5.x) vía adapter pattern + rate limiting |
| **Reportes** | CSV + gráficos Plotly (PNG, HTML interactivo, JSON) |

---

## Paleta de colores

| Modo | Primario | Secundario | Fondo | Texto | Grid |
|---|---|---|---|---|---|
| **Claro** | `#ED3237` (Rojo UT) | `#00A859` (Verde UT) | `#FFFFFF` | `#111827` | `#E5E7EB` |
| **Oscuro** | `#00A859` (Verde) | `#ED3237` (Rojo) | `#1E1E2E` | `#CDD6F4` | `#313244` |

Los colores de la marca se definen en `utils/theme.ts` como `DARK_THEME_VARS` y `LIGHT_THEME_VARS`. El tema oscuro usa la paleta Catppuccin Mocha. El toggle aplica los colores imperativamente vía `style.setProperty` sobre `:root`.

---

## Arquitectura

```
┌──────────────────┐
│   Frontend       │  Deno Fresh + Preact + Signals
│   Islands Arch.  │  Islands (fetch + estado), Components (presentación), Utils (helpers)
└────────┬─────────┘
         │ HTTP (JWT)
┌────────▼─────────┐     ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Backend        │────▶│  Repositories │────▶│   PostgreSQL     │     │    Moodle    │
│   FastAPI         │     │  (CRUD puro)  │     │                  │     │  API REST    │
│   API Endpoints   │     └──────────────┘     └──────────────────┘     └──────┬───────┘
└────────┬─────────┘                                                          │
         │ Redis                                                              │
┌────────▼─────────┐     ┌──────────────┐                                    │
│  Celery Worker   │────▶│  Phases      │  Pipeline ETL:                     │
│  (tasks.py)      │     │  (Consult,   │  ConsultPhase → AnalyzePhase →     │
│                  │     │   Analyze,   │  StructurePhase → PeoplePhase    │
│                  │     │   Execute)   │                                    │
└────────┬─────────┘     └──────┬───────┘                                    │
         │                      │                                            │
┌────────▼─────────┐            │                                            │
│  Celery Beat     │            │                                            │
│  (cleanup)       │            │                                            │
└──────────────────┘            └────────────────────────────────────────────┘
```

**Backend:** Endpoints → Repositories (datos) + Workers (Celery) → Phases (ETL) → MoodleService + MoodleIntegration. Las fases implementan el patrón Pipeline con Shared Context (`PhaseContext`). Los repositorios son funciones puras (no clases) que reciben `db` como primer parámetro.

**Frontend:** Islands Architecture sobre Preact + Signals. Las islas (`islands/`) manejan fetch y estado. Los componentes (`components/`) son presentacionales puros. Los utils (`utils/`) contienen señales globales (`darkSignal`, `profileSignal`), constantes compartidas (`STATUS_COLORS`, `DARK_VARS`) y helpers.

---

## Módulo de Novedades (ETL — 5 fases)

Sube un Excel de carga académica y sincroniza cursos, categorías, usuarios y matrículas con Moodle.

| Fase | Clase | Descripción | Progreso |
|---|---|---|---|
| **FASE 1** | `ConsultPhase` | Parsear Excel + consultar Moodle (categorías, cursos, usuarios). Resuelve docentes por email en batch. | 0% → 20% |
| **FASE 2** | `AnalyzePhase` | Comparar cursos contra Moodle con matching en 3 niveles (exacto → base key → core key). Determina crear, eliminar, activar, ocultar o renombrar. | 20% → 34% |
| **FASE 3** | `process_etl_phase` | Ejecutar cambios estructurales vía Celery chords en 2 oleadas: (1) delete, (2) activate, hide, rename, create cursos. | 34% → 62% |
| **FASE 4** | `process_etl_phase` | Crear usuarios nuevos en Moodle + matricular docentes como editingteacher en sus cursos vía Celery chord. | 65% → 85% |
| **FASE 5** | `ReportService` | Generar 14 CSVs + 5 gráficos Plotly + ZIP con todo. | 85% → 100% |

### Destacados

- **Checkpointing por fase:** si Celery crashea en FASE 3, el retry restaura FASE 1–2 desde BD y reanuda desde FASE 3. Sin re-procesar trabajo ya hecho.
- **Guard de delete masivo:** si el plan incluye >500 eliminaciones, la ejecución se pausa en `review_required` y requiere confirmación explícita vía `POST /api/v1/jobs/{id}/confirm`. Umbral configurable con `MAX_AUTO_DELETE_COURSES`.
- **Creación de usuarios:** `createpassword=1` — Moodle genera la contraseña y la envía por email. No se almacena la cédula como password.
- **Resolución batch de docentes:** 1 sola llamada a `core_user_get_users_by_field` con todos los emails, en vez de N llamadas individuales.
- **Compatibilidad Moodle 3.9:** adapter pattern para diferencias entre versiones (sin `enrolment_1`, `templatecourse` como `int`, `createpassword` en vez de `preferences[]`, `categoryid` con fallback multi-nivel).

**Archivos clave:** `workers/tasks.py` (orquestador), `workers/phases/phase1_consult.py`, `phase2_analyze.py`, `phase3_structure.py`, `phase4_people.py`, `repositories/` (DB), `integrations/moodle.py` (MoodleIntegration), `services/moodle.py` (MoodleService), `services/moodle_adapter.py`, `services/course_comparison.py`, `services/parsers/distancia.py`, `services/reports.py`, `services/charts.py`.

---

## Módulo de Operaciones (CRUD masivo + consultas)

### Creación y eliminación masiva

Sube archivos CSV para crear o eliminar entidades en lote.

| Operación | Endpoint | CSV requerido |
|---|---|---|
| **Mostrar/Ocultar cursos** | `POST /operations/courses/visibility?visibility=show\|hide` | `shortname` |
| **Crear usuarios** | `POST /operations/users/create-csv` | `username, firstname, lastname, email, role1, password, forcepasswordchange` |
| **Crear categorías** | `POST /operations/categories/create-csv` | `name, idnumber, parent, description, visible` |
| **Eliminar cursos** | `POST /operations/courses/upload-csv` | `shortname` |
| **Eliminar usuarios** | `POST /operations/users/upload-csv` | `username` |
| **Eliminar categorías** | `POST /operations/categories/upload-csv` | `idnumber` |

Procesado por `operations_tasks.py` (Celery). El estado se consulta en `GET /operations/batch/{id}/status`.

### Consultas asíncronas

Consulta cursos, categorías y usuarios en Moodle sin timeout HTTP (Celery con `task_time_limit=300`).

| Operación | Endpoint |
|---|---|
| Encolar consulta | `POST /queries/{entity}` |
| Estado + resultado | `GET /queries/tasks/{id}` |
| Descargar CSV | `GET /queries/tasks/{id}/download` |

Procesado por `query_tasks.py` (Celery).

---

## Interfaz de usuario

### Sidebar con 4 tarjetas principales

| Tarjeta | Hub page | Sub-opciones |
|---|---|---|
| **Usuarios** | `/usuarios` | Consultar, Crear, Eliminar |
| **Cursos** | `/cursos` | Consultar, Crear, Eliminar, Visibilidad |
| **Categorías** | `/categorias` | Consultar, Crear, Eliminar |
| **Operaciones** | `/operaciones` | Ejecuciones, Histórico |

Cada hub page muestra tarjetas con icono, título y descripción. Al hacer clic en una sub-opción, navega a la ruta funcional correspondiente.

### Páginas principales

| Ruta | Contenido |
|---|---|
| `/dashboard` | KPI cards, minigráfico SVG, última ejecución, tabla de ejecuciones recientes |
| `/cursos/crear` | FileUploader — sube Excel y lanza ETL |
| `/cursos/consultar` | QueryTable — búsqueda de cursos por shortname con match parcial |
| `/cursos/eliminar` | CsvUploader — eliminación masiva de cursos vía CSV |
| `/cursos/visibilidad` | BulkVisibilityIsland — mostrar/ocultar cursos masivamente vía CSV |
| `/usuarios/crear` | CsvUploader — creación masiva de usuarios |
| `/usuarios/consultar` | QueryTable — búsqueda de usuarios por username/email |
| `/usuarios/eliminar` | CsvUploader — eliminación masiva de usuarios |
| `/categorias/crear` | CsvUploader — creación masiva de categorías |
| `/categorias/consultar` | QueryTable — búsqueda de categorías por idnumber |
| `/categorias/eliminar` | CsvUploader — eliminación masiva de categorías |
| `/operaciones/ejecuciones` | Tabs (Crear/Eliminar Cursos/Usuarios/Categorías) con ExecutionList + OperationList |
| `/operaciones/historico` | Tabs con gráficos Plotly theme-aware + tabla de datos |
| `/jobs/{id}` | Detalle de ejecución con progreso en vivo, métricas, errores paginados |
| `/reportes?execution_id={id}` | Descarga de 14 CSVs + 5 gráficos Plotly |

### Islas principales

| Isla | Función |
|---|---|
| `ExecutionList` | Tabla de ejecuciones ETL con filtros, paginación, acciones (Procesar, Eliminar, ZIP, Reportes) |
| `OperationList` | Tabla de lotes con filtros bloqueables por entidad/acción |
| `DashboardIsland` | KPI cards, minigráfico, semáforo, ejecuciones recientes |
| `CsvUploader` | Formulario genérico de carga CSV con validación y polling de progreso |
| `BulkVisibilityIsland` | Selector mostrar/ocultar + carga CSV + polling de progreso de visibilidad de cursos |
| `QueryTable` | Búsqueda asíncrona con polling y descarga CSV |
| `HistoricoIsland` | Evolución semestral y comparación con Chart.js |
| `OperationHistorico` | Gráfico Plotly theme-aware con métricas adaptativas por operación |
| `Sidebar` | Navegación con 4 tarjetas (Usuarios, Cursos, Categorías, Operaciones), avatar, ThemeToggle |
| `JobDetailIsland` | Progreso en vivo con polling, métricas, errores paginados |

### Componentes compartidos

| Componente | Dónde se usa |
|---|---|
| `HubCard` | 4 hub pages (usuarios, cursos, categorias, operaciones) — tarjeta con icono, título, descripción |
| `ErrorBox` | 8+ islas — mensaje de error con icono |
| `Pagination` | ExecutionList, OperationList — anterior/siguiente |
| `LoadingSkeleton` | 6+ islas — variantes `table`, `chart`, `kpi` |
| `KpiCard`, `MiniBarChart` | DashboardIsland |
| `YearNav`, `SemesterPicker`, `SemesterMultiPicker` | HistoricoIsland, SemesterComparison |
| `Layout`, `ProgressBar`, `Card`, `Button`, `Input`, `Toast` | Varios |

---

## Estructura del proyecto

```
SIAUGESMAT/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # auth, jobs, upload, analytics, reports, charts, operations, queries
│   │   ├── analytics/          # metrics.py (métricas agregadas, semáforo)
│   │   ├── core/               # config.py, security.py, dependencies.py
│   │   ├── db/                 # models.py, session.py, base.py
│   │   ├── integrations/       # moodle.py (MoodleIntegration — orquestación alto nivel)
│   │   ├── repositories/       # execution_repo, log_repo, query_repo, operation_repo (CRUD puro)
│   │   ├── schemas/            # Pydantic schemas (job, analytics, operations, upload, user)
│   │   ├── services/           # moodle.py (MoodleService), etl.py, course_comparison.py,
│   │   │                       # reports.py, charts.py, parsers/ (DistanciaParser, patterns)
│   │   │                       # moodle_adapter.py, rate_limiter.py
│   │   ├── workers/            # tasks.py (ETL), phases/ (phase1_consult, phase2_analyze),
│   │   │                       # operations_tasks.py, query_tasks.py, cleanup_tasks.py, etl_item_task.py
│   │   ├── scripts/            # bulk_course_visibility.py (CLI para mostrar/ocultar cursos en lote)
│   │   ├── celery_app.py       # Config Celery + beat schedule
│   │   └── main.py
│   ├── tests/                  # 177 tests (ETL, repos, phases, pipeline, analytics, API)
│   ├── alembic/                # Migraciones de base de datos
│   ├── reports/                # Reportes generados (CSV, ZIP)
│   ├── uploads/                # Archivos Excel subidos
│   └── requirements.txt
├── frontend/
│   ├── components/             # Button, Input, Card, Layout, ProgressBar, Toast,
│   │                           # ErrorBox, Pagination, LoadingSkeleton, KpiCard, MiniBarChart,
│   │                           # YearNav, SemesterPicker, SemesterMultiPicker, ReportsSection
│   ├── islands/                # Sidebar, ThemeToggle, DashboardIsland, ExecutionList,
│   │                           # OperationList, OperationHistorico, HistoricoIsland,
│   │                           # FileUploader, CsvUploader, QueryTable, CrearUsuarios,
│   │                           # JobDetailIsland, ReportesIsland, Chart, MetricsChart,
│   │                           # SemesterComparison, LoginForm, LoginPageIsland, UploadIsland
│   ├── routes/                 # _app.tsx, _middleware.ts, index.tsx, login.tsx, dashboard.tsx
│   │   ├── usuarios/           # index.tsx (hub), consultar.tsx, crear.tsx, eliminar.tsx
│   │   ├── cursos/             # index.tsx (hub), consultar.tsx, crear.tsx, eliminar.tsx, visibilidad.tsx
│   │   ├── categorias/         # index.tsx (hub), consultar.tsx, crear.tsx, eliminar.tsx
│   │   ├── operaciones/        # index.tsx (hub), ejecuciones.tsx, historico.tsx
│   │   ├── jobs/               # [id].tsx
│   │   ├── reportes.tsx        # Redirects: ejecuciones.tsx, historico.tsx, upload.tsx
│   ├── services/api.ts         # Barrel re-export → api/ (types, core, auth, jobs, analytics, reports, operations, queries, mantenimiento)
│   ├── utils/                  # theme.ts, plotly.ts, profile.ts, operations-tabs.ts, constants.ts,
│   │                           # auth.ts, auth-guard.ts, cache.ts, date.ts, icons.tsx, toast.ts, reports.ts
│   ├── static/styles.css       # Estilos globales, animaciones, responsive
│   ├── deno.json               # Configuración Fresh + dependencias
│   └── fresh.gen.ts            # Manifest de rutas (generado por build)
├── docker-compose.yml          # 7 servicios: db, redis, backend, worker, beat, frontend, nginx
├── docker-compose.override.yml  # Puertos expuestos + volume mount para desarrollo
├── e2e/                        # Pruebas end-to-end contra Moodle real
│   ├── fixtures/               #   .xlsx con datos reales (protegidos por .gitignore)
│   ├── run_test.py             #   Script unificado (upload + process + verify)
│   └── README.md
├── .env.example                # Variables de entorno de ejemplo
└── README.md
```

---

## Requisitos

### Producción (Docker)
- Docker 24+
- Docker Compose 2.20+

### Desarrollo local

| Herramienta | Versión |
|---|---|
| Python | 3.12+ |
| Deno | 2.5+ |
| PostgreSQL | 17 |
| Redis | 7 |

---

## Desarrollo local

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
copy .env.example .env     # Configurar credenciales
```

### 2. Infraestructura

```bash
docker compose up -d db redis
```

> **Docker Desktop en Windows:** Si las imágenes grandes (`python:3.12.10-slim`, `denoland/deno:2.5.6`) fallan con `lookup production.cloudfront.docker.com: no such host`, agregá `"dns": ["8.8.8.8", "1.1.1.1"]` en Docker Desktop → Settings → Docker Engine → Apply & Restart.

### 3. Migraciones

```bash
cd backend
alembic stamp head     # init_db() ya crea las tablas. Usar stamp, no upgrade.
```

> **Nota:** `init_db()` crea las tablas automáticamente al arrancar. Usá `stamp head` en vez de `upgrade head` para marcar la versión sin intentar recrear tablas existentes.

### 4. Servicios

```bash
# Terminal 1 — Backend API
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Worker Celery (ETL + operaciones)
cd backend
celery -A app.celery_app worker --loglevel=info --concurrency=1

# Terminal 3 — Celery Beat (limpieza periódica)
cd backend
celery -A app.celery_app beat --loglevel=info

# Terminal 4 — Frontend
cd frontend
deno task start
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Documentación API: http://localhost:8000/docs

---

## Variables de entorno principales

```ini
# Base de datos
DATABASE_URL=postgresql://user:pass@localhost:5432/siaugesmat

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=genera-una-clave-segura-aqui

# Moodle por modalidad
MOODLE_URL__PRESENCIAL=https://...
MOODLE_TOKEN__PRESENCIAL=token...
MOODLE_VERSION__PRESENCIAL=3.8

MOODLE_URL__DISTANCIA=https://...
MOODLE_TOKEN__DISTANCIA=token...
MOODLE_VERSION__DISTANCIA=3.9

# Plantilla de curso (obligatorio para crear cursos)
DEFAULT_COURSE_TEMPLATE=PORTAFOLIO_TEMPLATE

# Umbrales del semáforo
ANALYTICS_ERROR_THRESHOLD_YELLOW=1.0
ANALYTICS_ERROR_THRESHOLD_RED=5.0
ANALYTICS_MAX_DURATION_YELLOW=3600
ANALYTICS_MAX_DURATION_RED=7200

# CORS
CORS_ORIGINS=http://localhost:3000

# Rate limiting contra Moodle
MOODLE_MAX_REQUESTS_PER_SECOND=5
MOODLE_BURST_SIZE=10

# Otros
DEBUG=false
JOB_TIMEOUT=28800
MAX_AUTO_DELETE_COURSES=500
```

Los archivos `.env.example` en la raíz y en `backend/` contienen todas las variables con valores de ejemplo. Copiarlos a `.env` y ajustar credenciales reales.

---

## Tests

### Backend (177 tests)

```bash
cd backend
pytest -v
pytest --cov=app          # con cobertura
```

Cubre: parser ETL, repositorios (execution, log, query, operation), fases del pipeline (Consult, Analyze, Structure, People), integración del pipeline completo, endpoints API, analítica y semáforo.

### End-to-end (contra Moodle real)

```bash
# Modo seguro — solo usuarios (no toca cursos)
python e2e/run_test.py e2e/fixtures/ibague.xlsx

# Modo completo con confirmación de delete masivo
python e2e/run_test.py e2e/fixtures/uraba.xlsx --mode both --confirm
```

---

## Despliegue con Docker

```bash
# Construir e iniciar todos los servicios
docker compose up --build -d

# Ver logs
docker compose logs -f

# Detener
docker compose down
```

El `docker-compose.yml` incluye 7 servicios:

| Servicio | Imagen | Puerto | Función |
|---|---|---|---|
| `db` | `postgres:17` | — | Base de datos (solo red interna) |
| `redis` | `redis:7-alpine` | — | Cola de tareas (solo red interna) |
| `backend` | `siaugesmat-backend` | — | API FastAPI |
| `worker` | `siaugesmat-backend` | — | Worker Celery (ETL + operaciones) |
| `beat` | `siaugesmat-backend` | — | Celery Beat (limpieza cada 6h) |
| `frontend` | `siaugesmat-frontend` | — | Servidor Fresh con Deno |
| `nginx` | `nginx:alpine` | 80, 443 | Reverse proxy HTTPS — único punto de entrada público |

### SSL / HTTPS

Colocar los certificados en `certs/` (no se comitean):

```bash
mkdir certs
# Copiar archivos:
#   certs/fullchain.pem — certificado completo
#   certs/privkey.pem   — clave privada
```

Para pruebas con certificados autofirmados:

```bash
mkdir certs
docker run --rm -v "${PWD}/certs:/certs" alpine/openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 -keyout /certs/privkey.pem -out /certs/fullchain.pem \
  -subj "/CN=localhost"
```

> En Windows PowerShell, usar `${PWD}` en vez de `$(pwd)`.

### Desarrollo local vs producción

Para desarrollo local (puertos expuestos), crear un override:

```bash
# docker-compose.override.yml
services:
  db:
    ports: ["5432:5432"]
  redis:
    ports: ["6379:6379"]
  backend:
    ports: ["8000:8000"]
  frontend:
    ports: ["3000:3000"]
```

`docker compose up` leerá automáticamente el override y expondrá los puertos para desarrollo.
