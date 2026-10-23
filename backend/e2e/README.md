# Pruebas del pipeline ETL contra Moodle

Scripts para probar el pipeline ETL completo contra la instancia real de Moodle
(`tuaulavirtual.ut.edu.co`) o contra un Moodle **simulado** (HTTP mock local).

## Requisitos

- Backend corriendo (`docker compose up -d backend worker`)
- Python 3.12 con dependencias del backend instaladas

## Fixtures (archivos Excel de carga académica)

Los archivos de carga (`*.xlsx`) contienen **datos reales de docentes**, por lo que **no se comitean**.
Cada integrador debe colocar los suyos en `backend/e2e/fixtures/` antes de ejecutar:

```bash
# Desde la raíz del backend
mkdir -p e2e/fixtures
# Coloca aquí tu(s) archivo(s) de carga académica real o de prueba
```

Solo se comitean los scripts (`ejecutar_test.py`, `ayudante_jwt.py`,
`moodle_simulado.py`, `ejecutar_simulado.py`, `levantar_stack_e2e.py`,
`stack_e2e.py`) y esta documentación.

## Uso (Moodle real)

```bash
# Modo seguro — solo usuarios (no toca cursos)
python e2e/ejecutar_test.py e2e/fixtures/MI_CARGA.xlsx

# Modo users + courses — requiere confirmación de delete masivo
python e2e/ejecutar_test.py e2e/fixtures/MI_CARGA.xlsx --mode both

# Con confirmación automática del delete masivo
python e2e/ejecutar_test.py e2e/fixtures/MI_CARGA.xlsx --mode both --confirm

# Semestre personalizado
python e2e/ejecutar_test.py e2e/fixtures/MI_CARGA.xlsx --semester 2026B --mode users

# Backend en otro puerto
python e2e/ejecutar_test.py e2e/fixtures/MI_CARGA.xlsx --url http://localhost:8001
```

## Modo simulado (sin Moodle real)

Levanta un **HTTP mock de Moodle** (`moodle_simulado.py`, stdlib, sin dependencias)
y apunta un backend + worker aislados hacia él. Ideal para CI/staging o para
probar el pipeline sin tocar la instancia real.

```bash
# 1) BD PostgreSQL fresca y migrada
createdb siaugesmat_e2e
alembic upgrade head

# 2) Fake Moodle en localhost:8800
python e2e/moodle_simulado.py --port 8800

# 3) Worker aislado (env: BD e2e + Redis índice 5 + fake Moodle)
$env:DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/siaugesmat_e2e"
$env:REDIS_URL="redis://localhost:6380/5"
$env:MOODLE_URL__DISTANCIA="http://localhost:8800"
$env:MOODLE_TOKEN__DISTANCIA="tokendemo"
$env:MOODLE_VERSION__DISTANCIA="3.9"
celery -A app.celery_app.celery_app worker --loglevel=info --pool=solo

# 4) API aislada en :8001 (mismo env + UPLOAD_DIR/REPORT_DIR temporales)
$env:UPLOAD_DIR="$env:TEMP\siaugesmat_e2e_uploads"
$env:REPORT_DIR="$env:TEMP\siaugesmat_e2e_reports"
uvicorn app.main:app --port 8001

# 5) Correr el e2e
python e2e/ejecutar_test.py e2e/fixtures/ibague.xlsx --mode users --url http://localhost:8001
```

El mock registra cada request (wsfunction + payload) en stdout, de modo que se
puede verificar qué creó/actualizó el pipeline.

### Levantar/detener el stack con un solo comando

**Modo recomendado:** `ejecutar_simulado.py` levanta el mock + worker + API, corre
el e2e end-to-end y limpia solo:

```bash
# Desde la raíz del backend
python e2e/ejecutar_simulado.py                                    # default: ibague.xlsx --mode users
python e2e/ejecutar_simulado.py e2e/fixtures/MI_CARGA.xlsx --mode both --confirm
python e2e/ejecutar_simulado.py e2e/fixtures/MI_CARGA.xlsx --mode users --reset-db
```

- Los logs de mock/worker/API y del runner quedan en `e2e/tmp_reports/`
  (`runner_<fecha>.log`, `moodle.log`, `worker.log`, `api.log`). Con `--quiet`
  los daemons no vuelcan logs (a `DEVNULL`).

- Requiere la BD `siaugesmat_e2e` migrada (`alembic upgrade head`) y Redis local.
- `--reset-db` trunca las tablas de la BD e2e (derivadas del metadata de
  SQLAlchemy) para dejar el estado limpio antes de correr (recomendado entre
  corridas).
- `--mantener` deja mock/worker/API vivos al final (para inspección).

**Alternativa manual** (`levantar_stack_e2e.py`): lanza los servicios 2-4
**desacoplados** (`DETACHED_PROCESS`) y retorna al instante:

```bash
# Desde la raíz del backend
python e2e/levantar_stack_e2e.py              # mock :8800 + worker + API :8001
python e2e/levantar_stack_e2e.py --stop       # detiene los árboles registrados
```

- Los PIDs se guardan en `%TEMP%\siaugesmat_e2e\stack.pids.json` y los logs en
  `%TEMP%\siaugesmat_e2e\` (`moodle.log`, `worker.log`, `api.log`).
- El entorno del stack (BD `siaugesmat_e2e`, Redis índice 5, mock de Moodle,
  uploads/reports) se arma en `e2e/stack_e2e.py` y lo comparten ambos scripts;
  las variables `MOODLE_*__<modalidad>` SIEMPRE apuntan al mock (aislamiento).
- **Importante (Windows):** para lanzar estos servicios desde un tool `bash` de
  opencode, no usar `Start-Process` (hereda el pipe de stdout y la llamada queda
  `running` para siempre). Usar siempre este helper.

## Funcionamiento

1. `ayudante_jwt.py` genera un token JWT firmado (sin login Moodle)
2. `ejecutar_test.py` sube el Excel, dispara el ETL y espera resultados
3. Si el plan incluye >500 eliminaciones, se detiene y pide `--confirm`

## Salida

```
SIAUGESMAT — Prueba real
  Archivo:   MI_CARGA.xlsx
  Mode:      users
  Semestre:  2026B

Subiendo archivo...
  Upload OK → execution_id=14
Procesando...
  [running] 2% Consultando categorías…
  [running] 14% Análisis de datos completado
  [completed] 100% Ejecución completada

==================================================
Resultados — Ejecución #14
  Status:     completed
  Progreso:   100%
  Duración:   42.0s
  Errores:    0
  users_created:  0

✅ Pipeline completado exitosamente.
```