"""
Enrutador principal de la versión 1 de la API de SIAUGESMAT.

Agrupa todos los endpoints de los módulos:
- auth
- jobs
- upload
- analytics
"""

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, auth, charts, jobs, operations, queries, reports, upload

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["autenticación"])
router.include_router(jobs.router, prefix="/jobs", tags=["ejecuciones"])
router.include_router(upload.router, prefix="/upload", tags=["subida de archivos"])
router.include_router(analytics.router, prefix="/analytics", tags=["analítica y semáforo"])
router.include_router(reports.router, prefix="/reports", tags=["reportes"])
router.include_router(charts.router, prefix="/analytics", tags=["gráficos"])
router.include_router(operations.router, prefix="/operations", tags=["operaciones masivas"])
router.include_router(queries.router, prefix="/queries", tags=["consultas"])