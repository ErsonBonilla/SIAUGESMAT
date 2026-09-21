from fastapi import APIRouter

from app.api.v1.endpoints import (
    analitica,
    autenticacion,
    consultas,
    control_lotes,
    graficos,
    listado_lotes,
    novedades,
    operaciones,
    reportes,
    subida,
    trabajos,
)

router = APIRouter()

router.include_router(autenticacion.router, prefix="/auth", tags=["autenticación"])
router.include_router(trabajos.router, prefix="/jobs", tags=["ejecuciones"])
router.include_router(subida.router, prefix="/upload", tags=["subida de archivos"])
router.include_router(analitica.router, prefix="/analytics", tags=["analítica y semáforo"])
router.include_router(reportes.router, prefix="/reports", tags=["reportes"])
router.include_router(graficos.router, prefix="/analytics", tags=["gráficos"])
router.include_router(operaciones.router, prefix="/operations", tags=["operaciones masivas"])
router.include_router(consultas.router, prefix="/queries", tags=["consultas"])
router.include_router(control_lotes.router, prefix="/operations", tags=["operaciones masivas"])
router.include_router(listado_lotes.router, prefix="/operations", tags=["operaciones masivas"])
router.include_router(novedades.router, prefix="/novedades", tags=["novedades"])
