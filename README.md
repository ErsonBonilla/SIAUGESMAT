# 🎓 SIAUGESMAT

**Sistema de Integración y Automatización para la Gestión de Matrículas en Moodle**

Aplicación full-stack para la Universidad del Tolima que automatiza la carga masiva de cursos, usuarios y matriculaciones en **Tu Aula (Moodle 3.9)**. Procesa archivos Excel semestrales mediante el **Módulo de Novedades** (ETL de 5 fases) e incluye un **Módulo de Operaciones** para creación y eliminación masiva de entidades, consultas asíncronas, 16 reportes CSV con información detallada, 5 gráficos profesionales, dashboard de analítica y semáforos de estado en tiempo real.

---

## Stack tecnológico

| Capa | Tecnología |
|---|---|
| **Frontend** | Deno 2 + Fresh + Preact + Signals + Chart.js |
| **Backend** | Python 3.12 + FastAPI + SQLAlchemy + Celery + Redis |
| **Base de datos** | PostgreSQL 18 |
| **Cola de tareas** | Redis 8 + Celery (+ Celery Beat para tareas periódicas) |
| **Integración Moodle** | API REST (versiones 3.8 a 5.x) vía adapter pattern + rate limiting |
| **Reportes** | CSV + gráficos (PNG, HTML, JSON) + ZIP |
| **Calidad de código** | Backend: ruff + vulture; Frontend: `deno task check` (fmt + lint + typecheck) + CI en GitHub Actions |

---

## Paleta de colores

| Modo | Primario | Secundario | Fondo | Texto | Grid |
|---|---|---|---|---|---|
| **Claro** | `#ED3237` (Rojo UT) | `#00A859` (Verde UT) | `#FFFFFF` | `#111827` | `#E5E7EB` |
| **Oscuro** | `#00A859` (Verde) | `#ED3237` (Rojo) | `#1E1E2E` | `#CDD6F4` | `#313244` |

Los colores de la marca se definen en `utils/tema.ts` como `VARIABLES_TEMA_OSCURO` y `VARIABLES_TEMA_CLARO`. El tema oscuro usa la paleta Catppuccin Mocha. El toggle aplica los colores imperativamente vía `style.setProperty` sobre `:root`.

---

## Arquitectura

```
┌──────────────────┐
│   Frontend       │  Deno Fresh + Preact + Signals
│   Islands Arch.  │  Islands (fetch + estado), Components (presentación), Utils (helpers)
└────────┬─────────┘
         │ HTTP (Cookie HttpOnly JWT + X-CSRF-Token)
┌────────▼─────────┐     ┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Backend        │────▶│  Repositories │────▶│   PostgreSQL     │     │    Moodle    │
│   FastAPI         │     │  (CRUD puro)  │     │                  │     │  API REST    │
│   API Endpoints   │     └──────────────┘     └──────────────────┘     └──────┬───────┘
└────────┬─────────┘                                                          │
         │ Redis                                                              │
┌────────▼─────────┐     ┌──────────────┐                                    │
│  Celery Worker   │────▶│  Phases      │  Pipeline ETL:                     │
│  (tareas.py)     │     │  (Consulta,  │  FaseConsulta → FaseAnalisis →     │
│                  │     │   Análisis,  │  Fase 3 → Fase 4                   │
│                  │     │   Ejecución) │                                    │
└────────┬─────────┘     └──────┬───────┘                                    │
         │                      │                                            │
┌────────▼─────────┐            │                                            │
│  Celery Beat     │            │                                            │
│  (limpieza)      │            │                                            │
└──────────────────┘            └────────────────────────────────────────────┘
```

**Backend:** Endpoints → Repositories (datos) + Workers (Celery) → Phases (ETL) → ServicioMoodle + IntegracionMoodle. Las fases implementan el patrón Pipeline con Shared Context (`ContextoFase`). Los repositorios son funciones puras (no clases) que reciben `db` como primer parámetro.

**Núcleo puro (`app/pipeline/`):** todas las transformaciones de negocio que no requieren I/O viven en `app/pipeline/` — un paquete 100 % puro (sin DB, HTTP, settings ni Celery), verificado por AST en `tests/test_pureza_pipeline.py`. Incluye `nombres_cortos.py` (parsing de códigos), `indice_cursos.py`, `comparacion_cursos/` (comparador de cursos con umbrales inyectables), `novedades.py`, `metricas.py`, `plan.py`, `progreso.py`, `categorias.py`, `usuarios.py` y `matriculaciones.py`. Los workers y tests consumen el núcleo directamente (los antiguos *shims* de `app/services/` fueron eliminados).

**Frontend:** Islands Architecture sobre Preact + Signals. Las islas (`islands/`) manejan fetch y estado. Los componentes (`components/`) son presentacionales puros. Los utils (`utils/`) contienen señales globales (`senalTemaOscuro`, `senalPerfil`), constantes compartidas (`COLORES_SEMAFORO`, `VARIABLES_TEMA_OSCURO`) y helpers.

---

## Módulo de Novedades (ETL — 5 fases)

Sube un Excel de carga académica y sincroniza cursos, categorías, usuarios y matrículas con Moodle.

> Además del pipeline ETL, el sistema incluye una herramienta de **Gestión de Novedades** en `/cursos/novedades` que permite comparar dos cargas académicas del mismo semestre (la ejecución anterior vs una nueva) y detectar cambios de profesores en cursos existentes (oculta curso viejo, crea curso nuevo para el nuevo profesor, o rehabilita un curso oculto si el nuevo profesor ya lo tenía asignado). Usa el endpoint `POST /api/v1/novedades/compare`.

| Fase | Clase / Función | Descripción | Progreso |
|---|---|---|---|
| **FASE 1** | `FaseConsulta` | Parsear Excel + consultar Moodle (categorías, cursos, usuarios). Resuelve docentes por email en batch. | 0% → 20% |
| **FASE 2** | `FaseAnalisis` | Comparar cursos contra Moodle con matching en 3 niveles (exacto → base key → core key). Determina crear, eliminar, activar, ocultar o renombrar. | 20% → 34% |
| **FASE 3** | `procesar_fase_etl` | Ejecutar cambios estructurales vía Celery chords en 2 oleadas: (1) delete, (2) activate, hide, rename, create cursos. | 34% → 62% |
| **FASE 4** | `procesar_fase_etl` | Crear usuarios nuevos en Moodle + matricular docentes como editingteacher en sus cursos vía Celery chord. | 65% → 85% |
| **FASE 5** | `ServicioReportes` | Generar 16 CSVs + 5 gráficos + ZIP con todo. | 85% → 100% |

### Destacados

- **Checkpointing por fase:** si Celery crashea en FASE 3, el retry restaura FASE 1–2 desde BD y reanuda desde FASE 3. Sin re-procesar trabajo ya hecho.
- **Guard de delete masivo:** si el plan incluye >500 eliminaciones, la ejecución se pausa en `review_required` y requiere confirmación explícita vía `POST /api/v1/jobs/{id}/confirm`. Umbral configurable con `MAX_AUTO_DELETE_COURSES`.
- **Creación de usuarios:** `createpassword=1` — Moodle genera la contraseña y la envía por email. No se almacena la cédula como password.
- **Resolución paralela de docentes:** hasta 10 consultas simultáneas a `core_enrol_get_enrolled_users` con semáforo asyncio, en vez de N llamadas secuenciales.
- **Consolidación de correos duplicados:** si un correo coincide con más de una cuenta en Moodle, la ejecución conserva la cuenta **más antigua**, usa su username tal cual (sin renombrar: **el username encontrado en Moodle nunca se renombra**, ni siquiera si difiere del prefijo del correo) y elimina automáticamente las cuentas **más recientes que no tengan cursos**. Salvaguarda: si el duplicado tiene cursos —o el webservice no expone `core_enrol_get_users_courses`— no se borra y queda en `pending_review` para revisión manual. Los usernames eliminados/pendientes se registran en el log `identity_by_email_duplicate` (criterio `oldest`).
- **Compatibilidad Moodle 3.9:** adapter pattern para diferencias entre versiones (sin `enrolment_1`, `templatecourse` como `int`, `createpassword` en vez de `preferences[]`, `categoryid` con fallback multi-nivel).

**Archivos clave:** `workers/tareas.py` (orquestador), `workers/utilidades.py` (runner async compartido `ejecutar_moodle_async`), `workers/phases/fase1_consulta.py`, `fase2_analisis.py`, `fase3_estructura.py`, `fase4_personas.py`, `pipeline/` (núcleo puro), `repositories/` (DB), `integrations/integracion_moodle.py` (`IntegracionMoodle`), `services/operaciones_moodle.py` (`ServicioMoodle`), `services/adaptador_moodle.py`, `services/parsers/distancia.py` (`ParserDistancia`), `services/reportes.py`, `services/graficos.py`, `services/servicio_metricas.py`, `services/orquestacion.py` (puente API→Celery).

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

Procesado por `tareas_operaciones.py` (Celery). El estado se consulta en `GET /operations/batch/{id}/status`.

### Consultas asíncronas

Consulta cursos, categorías, usuarios y docentes inactivos en Moodle sin timeout HTTP (Celery con `time_limit=3600`; la consulta de docentes inactivos puede tardar 15–20 min porque recorre todos los cursos SIAUGESMAT).

| Operación | Endpoint |
|---|---|
| Encolar consulta | `POST /queries/{entity}` |
| Estado + resultado | `GET /queries/tasks/{id}` |
| Descargar CSV | `GET /queries/tasks/{id}/download` |

**Entidades disponibles**:
- `courses` — filtros por shortname, estado (>6 meses sin uso; o sin docente/no matriculados), formato de código (5 o 6 segmentos)
- `categories` — búsqueda por idnumber
- `users` — búsqueda por username/email/nombre (coincidencia exacta; el webservice Moodle no expone búsqueda por substring ni listado completo de usuarios)
- `duplicate_emails` — correos con más de un usuario registrado. Moodle 3.9 no permite listar todos los usuarios, por lo que combina dos fuentes semilla (usernames de `registros_ejecucion` + matriculados en cursos SIAUGESMAT vía `core_enrol_get_enrolled_users`) y luego re-consulta cada correo candidato con `core_user_get_users_by_field` (field=email) para capturar TODAS las cuentas que lo comparten. Devuelve una fila por cuenta: email, username, nombres, apellidos, ID de Moodle y número de cuentas que comparten el correo. Sin filtro por dominio. Puede tardar 15–25 min.
- `inactive_teachers` — docentes (**editingteacher**) que no han accedido a sus cursos desde un corte: **por días** (1–30, default 15), **por meses** (1–12, default 1), **por años** (≥ 1, default 1, sin tope superior) o **por semestre** (ej. `2026A`). Se requiere exactamente un corte por consulta. Consulta todos los cursos SIAUGESMAT en Moodle, obtiene los profesores matriculados con su `lastcourseaccess` y los filtra por la fecha de corte (el semestre usa la fecha de inicio). Devuelve: nombre del docente, username, correo, curso, programa académico (código de 4 dígitos), CAT (prefijo de 3 letras) y días sin acceso. Procesado en lotes paralelos (5 cursos simultáneos).
- `inactive_courses` — cursos SIAUGESMAT **sin uso** desde un corte: **días** (1–30, default 15), **meses** (1–12, default 1), **años** (≥ 1, default 1) o **semestre** (ej. `2026A`); exactamente un corte por consulta. Usa el campo `timemodified` (última modificación) de cada curso y devuelve: shortname, nombre, categoría, programa, CAT, fechas de creación y última modificación, y días sin uso. Rápido: recorre `get_courses` una sola vez (sin consultar docentes por curso).

> **Nota sobre el webservice Moodle:** el servicio web de la universidad no habilita
> `core_role_assign_get_role_assignments` ni `core_user_search_identity`, por lo que la
> consulta de usuarios es de coincidencia exacta por campo y la de docentes inactivos
> recorre los cursos SIAUGESMAT uno a uno. Si la universidad habilita esas funciones
> (o migra a Moodle 4.x), ambas consultas se vuelven directas y mucho más rápidas.

**Filtros de cursos**: el endpoint `POST /queries/courses` acepta los parámetros `search` (búsqueda por shortname), `status` (`unused_6months` para cursos sin uso > 6 meses) y `pattern` para filtrar por formato de código:
- `6segments` → `CAL_0852_sIV_5031216_G-1_29114506` (6 segmentos separados por `_`)
- `5segments` → `CHA_0845_sVI_102131_G-1` (5 segmentos separados por `_`)

Procesado por `tareas_consultas.py` (Celery).

---

## Interfaz de usuario

### BarraLateral con 4 tarjetas principales

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
| `/panel` | KPI cards, minigráfico SVG, última ejecución, tabla de ejecuciones recientes |
| `/cursos/crear` | CargaIsland (SubirArchivoIsland) — sube Excel y lanza ETL. Incluye botón **Ejecución** que lleva a `/operaciones/ejecuciones?tab=crear_cursos` |
| `/cursos/novedades` | NovedadesIsland — compara dos cargas académicas del mismo semestre (re-parsing del Excel anterior), detecta cambios de asignación docente (profesores que ya no dictan el curso) y permite aplicar acciones: ocultar curso viejo + crear nuevo, o rehabilitar curso oculto del nuevo profesor |
| `/cursos/consultar` | CursosConsultas — **consulta normal**: TablaConsultaIsland (QueryTable) con filtros de shortname, estado (huérfanos) y formato de código; **cursos sin uso**: ConsultaCursosSinUso con cortes por días/meses/años/semestre |
| `/cursos/eliminar` | CsvUploader — eliminación masiva de cursos vía CSV |
| `/cursos/visibilidad` | VisibilidadMasivaIsland — mostrar/ocultar cursos masivamente vía CSV |
| `/usuarios/crear` | CsvUploader — creación masiva de usuarios |
| `/usuarios/consultar` | TablaConsultaIsland (QueryTable) + ConsultaDocentesSinAcceso + ConsultaCorreosDuplicados — búsqueda de usuarios por username/email (modo normal), consulta de **docentes que no han accedido a sus cursos** (por días, default 15, o por semestre), con datos de programa y CAT, y consulta de **correos duplicados** (más de un usuario con el mismo correo) |
| `/usuarios/eliminar` | CsvUploader — eliminación masiva de usuarios |
| `/categorias/crear` | CsvUploader — creación masiva de categorías |
| `/categorias/consultar` | TablaConsultaIsland (QueryTable) — búsqueda de categorías por idnumber |
| `/categorias/eliminar` | CsvUploader — eliminación masiva de categorías |
| `/operaciones/ejecuciones` | Tabs (Crear/Eliminar Cursos/Usuarios/Categorías) con ListaEjecucionesIsland (ExecutionList) + ListaOperacionesIsland (OperationList) |
| `/operaciones/historico` | Tabs con gráficos Chart.js theme-aware + tabla de datos |
| `/ejecuciones/{id}` | Detalle de ejecución con progreso en vivo, métricas, errores paginados |
| `/reportes?execution_id={id}` | Descarga de 16 CSVs + 5 gráficos |
| `/ingreso` | Página de inicio de sesión (LoginForm) |

### Islas principales

| Isla | Función |
|---|---|
| `ListaEjecucionesIsland` | Tabla de ejecuciones ETL con filtros, paginación, acciones (Procesar, Eliminar, ZIP, Reportes) |
| `ListaOperacionesIsland` | Tabla de lotes con filtros bloqueables por entidad/acción |
| `PanelIsland` | KPI cards, minigráfico, semáforo, ejecuciones recientes |
| `CsvUploader` | Formulario genérico de carga CSV con validación y polling de progreso |
| `VisibilidadMasivaIsland` | Selector mostrar/ocultar + carga CSV + polling de progreso de visibilidad de cursos |
| `TablaConsultaIsland` | Búsqueda asíncrona con polling y descarga CSV |
| `NovedadesIsland` | Subir Excel de nueva carga académica, comparar con la ejecución anterior del mismo semestre, detectar cambios de profesores y aplicar acciones (ocultar/crear/rehabilitar cursos) |
| `ConsultaDocentesSinAcceso` | Seleccionar corte (días de inactividad, default 15, o semestre) y consultar docentes editingteacher que no han accedido a sus cursos desde esa fecha, con resultados de programa y CAT |
| `ConsultaCorreosDuplicados` | Buscar correos con más de un usuario registrado en Moodle (combina logs de la app + matriculados en cursos SIAUGESMAT), con una fila por cuenta y el número de cuentas que comparten el correo |
| `ConsultaCursosSinUso` | Seleccionar corte (días/meses/años/semestre) y consultar cursos SIAUGESMAT sin uso (por `timemodified`), con datos del curso: programa, CAT, fechas y días sin uso |
| `CursosConsultas` | Tabs **Consulta normal**/**Cursos sin uso** para la página `/cursos/consultar` |
| `Historico` | Evolución semestral y comparación con Chart.js |
| `HistoricoOperaciones` | Gráfico Chart.js theme-aware con métricas adaptativas por operación |
| `BarraLateral` | Navegación con 4 tarjetas (Usuarios, Cursos, Categorías, Operaciones), avatar, `AlternadorTema` |
| `DetalleEjecucionIsland` | Progreso en vivo con polling, métricas, errores paginados |

### Componentes compartidos

| Componente | Dónde se usa |
|---|---|
| `TarjetaHub`, `PaginaHub` | 4 hub pages (`usuarios`, `cursos`, `categorias`, `operaciones`) — tarjeta con icono, título y descripción |
| `CajaError` | 8+ islas — mensaje de error con icono |
| `Paginacion` | `ListaEjecucionesIsland`, `ListaOperacionesIsland` — anterior/siguiente |
| `EsqueletoCarga` | 6+ islas — variantes `table`, `chart`, `kpi` |
| `TarjetaKpi`, `MiniGraficoBarras` | `PanelIsland` |
| `NavegacionAnios`, `SelectorSemestre`, `SelectorMultiplesSemestres` | `Historico`, `ComparacionSemestre` |
| `Disposicion`, `BarraProgreso`, `Tarjeta`, `Boton`, `Entrada`, `LimiteError` | Varios |

---

## Estructura del proyecto

```
SIAUGESMAT/
├── .github/workflows/ci.yml     # GitHub Actions: backend + frontend + migraciones (PostgreSQL)
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/   # autenticacion, trabajos, subida, analitica, reportes, graficos, operaciones, consultas, control_lotes, listado_lotes, novedades
│   │   ├── core/               # config.py, seguridad.py, dependencies.py, limitador_login.py, configuracion_entidades.py, configuracion_logging.py
│   │   ├── db/                 # modelos.py, sesion.py, base.py
│   │   ├── integrations/       # integracion_moodle.py (IntegracionMoodle — orquestación alto nivel)
│   │   ├── pipeline/           # Núcleo puro (sin I/O): nombres_cortos, indice_cursos, comparacion_cursos/,
│   │   │                       #   novedades, metricas, plan, progreso, categorias, usuarios, matriculaciones
│   │   ├── repositories/       # repositorio_ejecuciones, repositorio_registros, repositorio_consultas, repositorio_operaciones (CRUD puro)
│   │   ├── schemas/            # Pydantic schemas (trabajo, analitica, operaciones, subida, usuario, novedades, respuestas)
│   │   ├── services/           # operaciones_moodle.py (ServicioMoodle), cliente_moodle.py, errores_moodle.py,
│   │   │                       # manejador_errores_moodle.py, fabrica_moodle.py, adaptador_moodle.py,
│   │   │                       # servicio_metricas.py, proceso_etl.py, reportes.py, utilidades_reportes.py,
│   │   │                       # servicio_novedades.py, graficos.py, validador_csv.py, validacion_excel.py, roles.py,
│   │   │                       # limitador_tasa.py, servicio_reportes_lote.py, utilidades_categorias.py, mensajes_error.py,
│   │   │                       # orquestacion.py (puente API→Celery), parsers/ (distancia.py, fabrica.py, base.py)
│   │   ├── workers/            # tareas.py (ETL), phases/ (fase1_consulta, fase2_analisis, fase3_estructura,
│   │   │                       #   fase4_personas, tarea_item, orquestador, comunes, base)
│   │   │                       # tareas_operaciones.py, tareas_consultas.py, tareas_limpieza.py, utilidades.py
│   │   ├── celery_app.py       # Config Celery + beat schedule
│   │   └── main.py
│   ├── tools/                  # CLI de mantenimiento manual (fuera del paquete app/):
│   │                           #   visibilidad_masiva_cursos.py, diagnosticar_cursos_ocultos.py, diagnostico_sibate.py,
│   │                           #   corregir_usuarios_correo_duplicado.py, corregir_usuarios_auth_externa.py,
│   │                           #   restablecer_password_moodle.py, restaurar_nombres_originales.py
│   ├── tests/                  # 707 tests (ETL, repos, fases, pipeline, analítica, API, workers, contratos)
│   ├── alembic/                # Migraciones de base de datos
│   ├── reports/                # Reportes generados (CSV, ZIP)
│   ├── uploads/                # Archivos Excel subidos
│   ├── requirements.txt        # Dependencias de producción (sin pytest)
│   ├── requirements-dev.txt    # Dev: -r requirements.txt + ruff, vulture, pytest, pytest-asyncio
│   ├── ruff.toml               # Configuración de ruff (py312, reglas seleccionadas/ignoradas)
│   └── Dockerfile
├── frontend/
│   ├── components/             # Boton, Entrada, Tarjeta, Disposicion, BarraProgreso, CajaError, Paginacion,
│   │                           # EsqueletoCarga, TarjetaKpi, MiniGraficoBarras, NavegacionAnios, SelectorSemestre,
│   │                           # SelectorMultiplesSemestres, SeccionReportes, SeccionReportesLote, TarjetaReporte,
│   │                           # TarjetaHub, PaginaHub, PaginaConsulta, PaginaAccionCsv, BotonPeriodo,
│   │                           # BotonEjecucion, SelectorArchivo, AyudaConsulta, TablaProgresoLote,
│   │                           # SeccionHistorialOperaciones, BannerProcesoEnCurso, LimiteError
│   ├── islands/                # BarraLateral, AlternadorTema, PanelIsland, ListaEjecucionesIsland,
│   │                           # ListaOperacionesIsland, Historico, HistoricoOperaciones, HistoricoTabs,
│   │                           # EjecucionesTabs, SubirArchivoIsland, CsvUploader, TablaConsultaIsland,
│   │                           # CrearUsuarios, DetalleEjecucionIsland, Reportes, GraficoIsland,
│   │                           # GraficoMetricasIsland, ComparacionSemestre, FormularioLogin, PaginaLoginIsland,
│   │                           # CargaIsland, NovedadesIsland, ConsultaDocentesSinAcceso, ConsultaCursosSinUso,
│   │                           # ConsultaCorreosDuplicados, ConsultaInactivos, CursosConsultas, UsuariosConsultas,
│   │                           # VisibilidadMasivaIsland, DetalleLoteIsland, NotificacionIsland, BotonMenuMovil
│   ├── routes/                 # _app.tsx, _middleware.ts, index.tsx, ingreso.tsx, panel.tsx
│   │   ├── usuarios/           # index.tsx (hub), consultar.tsx, crear.tsx, eliminar.tsx
│   │   ├── cursos/             # index.tsx (hub), consultar.tsx, crear.tsx, novedades.tsx, eliminar.tsx, visibilidad.tsx
│   │   ├── categorias/         # index.tsx (hub), consultar.tsx, crear.tsx, eliminar.tsx
│   │   ├── operaciones/        # index.tsx (hub), ejecuciones.tsx, historico.tsx, lotes/[batchId].tsx
│   │   ├── ejecuciones/        # [id].tsx
│   │   └── reportes.tsx
│   ├── services/api.ts         # Barrel re-export → api/ (tipos, nucleo, autenticacion, trabajos, analitica, reportes, operaciones, consultas, mantenimiento, novedades)
│   ├── hooks/                  # useSubidaLote.ts, usePuertaSubida.ts, useReportes.ts, useConsultaTarea.ts
│   ├── utils/                  # tema.ts, grafico.ts, plotly-a-grafico.ts, perfil.ts, pestanas-operaciones.ts,
│   │                           # constantes.ts, autenticacion.ts, guarda-autenticacion.ts, csrf.ts, fechas.ts,
│   │                           # iconos.tsx, toast.ts, reportes.ts, configuracion-entidad.ts, etiquetas-lote.ts, disposicion.ts
│   ├── static/                 # styles.css, main.css, SIAUGESMAT.ico
│   ├── deno.json               # Configuración Fresh + tareas (check, test, build) + lint rules + lib DOM
│   └── deno.lock               # Lock de dependencias Deno
├── docker-compose.yml          # 8 servicios: db, redis, migrate, backend, worker, beat, frontend, nginx
├── docker-compose.override.yml  # Puertos expuestos + volume mount para desarrollo
├── backend/e2e/                 # Pruebas de integración contra Moodle real
│   ├── fixtures/                #   .xlsx con datos reales
│   ├── ejecutar_test.py         #   Script unificado
│   └── README.md
├── .env.example                # Variables de entorno de ejemplo (único, copiar al .env raíz)
├── certs/                      # Certificados SSL para HTTPS
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
| Deno | 2.9+ |
| PostgreSQL | 18 |
| Redis | 8 |

---

## Desarrollo local

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows
source .venv/bin/activate  # Linux/macOS
# Para desarrollo instalar requirements-dev.txt (incluye ruff, vulture y pytest).
# La imagen Docker de producción instala solo requirements.txt.
pip install -r requirements-dev.txt
# Las versiones exactas se fijan en requirements.lock / requirements-dev.lock
# (geradas con `uv pip compile`). Regenerarlas cuando cambie requirements*.txt:
#   uv pip compile requirements.txt -o requirements.lock
#   uv pip compile requirements-dev.txt -o requirements-dev.lock
# Copiar las variables de entorno a la RAÍZ del proyecto (config.py lee el .env raíz)
# desde la raíz:  copy .env.example .env
# Opcional: backend/.env solo para overrides de dev (p. ej. DATABASE_URL apuntando a localhost)
```

### 2. Infraestructura

```bash
docker compose up -d db redis
```

> **Redis:** el contenedor expone `6380` en el host (`6380:6379`) para evitar
> colisiones con servicios que ocupen el `6379` (p. ej. `svchost` en Windows).
> El `REDIS_URL` local de `.env.example` ya apunta a `localhost:6380`. Los
> servicios internos (`backend`, `worker`, `beat`) siguen usando la red interna
> de Docker (`redis://redis:6379/0`).

> **Docker Desktop en Windows:** Si las imágenes grandes (`python:3.12.10-slim`, `denoland/deno:2.9.5`) fallan con `lookup production.cloudfront.docker.com: no such host`, agregá `"dns": ["8.8.8.8", "1.1.1.1"]` en Docker Desktop → Settings → Docker Engine → Apply & Restart.

### 3. Migraciones

```bash
cd backend
alembic stamp head     # inicializar_db() ya crea las tablas. Usar stamp, no upgrade.
```

> **Nota:** `inicializar_db()` crea las tablas automáticamente solo en desarrollo
> (`DEBUG=true`). En el despliegue Docker el servicio `migrate` ejecuta
> `alembic upgrade head` automáticamente antes de que arranquen backend,
> worker y beat. En entornos locales donde las tablas ya existen (creadas por
> `inicializar_db()` sin marcar), usá `alembic stamp head` para sincronizar la
> versión sin recrear tablas.
>
> Validá que no haya drift entre modelos y BD con `alembic check` (la cadena
> completa se valida en el job `migraciones` del CI). Ver `AGENTS.md` para las
> convenciones de naming y los contratos que no deben renombrarse.

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
REDIS_URL=redis://localhost:6380/0

# JWT y rate limiting del login
JWT_SECRET_KEY=genera-una-clave-segura-aqui
JWT_EXPIRE_MINUTES=60
LOGIN_MAX_ATTEMPTS=5
LOGIN_WINDOW_SECONDS=300

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
CHORD_ACTIVE_MINUTES=15
STUCK_EXECUTION_TIMEOUT=21600
MOODLE_REQUEST_TIMEOUT=60.0
MOODLE_MAX_RETRIES=3
```

El archivo `.env.example` en la raíz contiene todas las variables con valores de ejemplo. Para el **despliegue Docker**, los valores se definen en el `.env` raíz (el `docker-compose.yml` solo referencia `${VAR}`). Para el **desarrollo local**, `config.py` lee el `.env` raíz como fuente principal y `backend/.env` como *override* solo para diferencias de dev (p. ej. `DATABASE_URL=postgresql://...@localhost:5432/...`). Los valores no deben duplicarse en el código ni en compose: solo el llamado a la variable.

---

## Tests y calidad de código

### Backend (707 tests)

```bash
cd backend
pytest -q                          # suite completa (SQLite temporal, sin .env)
```

> Los tests de integración real contra Moodle (`tests/test_integracion_real.py`) se
> excluyen por defecto (`-m "not integration"`); para ejecutarlos:
> `pytest -m integration` (requiere `.env` con credenciales de Moodle).

Cubre: parser ETL, repositorios, fases del pipeline, núcleo puro, integración, endpoints API, analítica, workers, tareas Celery, cliente Moodle, adaptadores y más.

> **Entorno de tests:** los tests corren por defecto contra una SQLite temporal
> (mismo comportamiento en local que en CI, evitando tocar bases reales). Para
> correr contra la base del `.env` hay que pedirlo explícitamente:
> `SIAUGESMAT_TESTS_USE_DOTENV=1 pytest` (con precaución: el fixture recrea el
> esquema en cada test).

### Frontend (Fresh/Deno)

```bash
cd frontend
deno task test           # 65 tests (utils, services, islands)
```

### Verificación estática

```bash
# Backend — lint + formato + código muerto + pureza del núcleo pipeline
cd backend
ruff check app tests alembic
ruff format --check app tests alembic
vulture app --min-confidence 70
pytest tests/test_pureza_pipeline.py -v

# Frontend — formato + lint + typecheck (equivalente a deno task check)
cd frontend
deno task check
deno task build
```

### End-to-end (contra Moodle real)

```bash
cd backend
# Modo seguro — solo usuarios (no toca cursos)
python e2e/ejecutar_test.py e2e/fixtures/ibague.xlsx

# Modo completo con confirmación de delete masivo
python e2e/ejecutar_test.py e2e/fixtures/uraba.xlsx --mode both --confirm
```

---

## Integración continua (GitHub Actions)

El flujo de CI en `.github/workflows/ci.yml` corre en cada push a `main` y en cada PR:

| Job | Pasos |
|---|---|
| **backend** | Python 3.12 → `ruff check app tests alembic` → `ruff format --check app tests alembic` → `vulture app --min-confidence 70` → `pytest -q` |
| **frontend** | Deno 2.9.5 → `deno task check` (fmt + lint + typecheck) → `deno test -A tests/` → `deno task build` |
| **migraciones** | PostgreSQL 18 → `alembic upgrade head` → `alembic check` (sin drift) → smoke de esquema y contratos |

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

El `docker-compose.yml` incluye 8 servicios:

| Servicio | Imagen | Puerto | Función |
|---|---|---|---|
| `db` | `postgres:18.6` | — | Base de datos (solo red interna) |
| `redis` | `redis:8.10.1-alpine` | 6380 (host, vía override) | Cola de tareas (solo red interna) |
| `migrate` | `siaugesmat-backend` | — | Aplica migraciones Alembic (`alembic upgrade head`) y termina |
| `backend` | `siaugesmat-backend` | — | API FastAPI |
| `worker` | `siaugesmat-backend` | — | Worker Celery (ETL + operaciones) |
| `beat` | `siaugesmat-backend` | — | Celery Beat (limpieza periódica) |
| `frontend` | `siaugesmat-frontend` | — | Servidor Fresh con Deno |
| `nginx` | `nginx:1.27-alpine` | 80, 443 | Reverse proxy HTTPS — único punto de entrada público |

> `migrate` corre una sola vez (`restart: "no"`) y `backend`, `worker` y
> `beat` esperan su finalización (`depends_on: migrate: condition:
> service_completed_successfully`) antes de arrancar.

### SSL / HTTPS

Colocar los certificados en `certs/` (no se comitean):

```bash
mkdir certs
# Copiar archivos:
#   certs/fullchain.pem — certificado completo
#   certs/privkey.pem   — clave privada
```

Para pruebas con certificados autofirmados (incluye SANs para `localhost`, `127.0.0.1` e IPs locales):

```bash
bash certs/generate-dev-certs.sh
```

> Ver `certs/README.md` para opciones adicionales (dominio público o generación vía contenedor Docker en Windows).

### Desarrollo local vs producción

Para desarrollo local (puertos expuestos y montaje en caliente), `docker-compose.override.yml` expone:

```yaml
# docker-compose.override.yml
services:
  db:
    ports: ["5432:5432"]
  redis:
    # 6380 en el host (el 6379 suele estar ocupado por svchost en Windows)
    ports: ["6380:6379"]
  backend:
    volumes:
      - ./backend/app:/app/app:ro
    ports: ["8100:8000"]
  worker:
    volumes:
      - ./backend/app:/app/app:ro
  frontend:
    ports: ["3000:3000"]
```

`docker compose up` leerá automáticamente el override y expondrá los puertos
para desarrollo. El backend Dockerizado queda accesible en
`http://localhost:8100` (mientras que el backend de desarrollo local corre
en `http://localhost:8000`).
