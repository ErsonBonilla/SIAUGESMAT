import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.repositories.repositorio_operaciones import (
    cancelar_lote,
    eliminar_lote,
    obtener_estado_lote,
    obtener_items_lote,
    obtener_lote,
    obtener_todos_items_lote,
    pausar_lote,
    reanudar_lote,
)
from app.schemas.operaciones import ItemOperacionSalida, RespuestaEstadoLote
from app.schemas.respuestas import (
    RespuestaAccionLote,
    RespuestaCancelacionLote,
    RespuestaListaReportesLote,
    RespuestaPausaLote,
    RespuestaReanudacionLote,
)
from app.schemas.usuario import UsuarioEnToken
from app.services.servicio_reportes_lote import (
    construir_zip_reportes_lote,
    guardar_reportes_lote,
    listar_reportes_lote,
    obtener_ruta_reporte_lote,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _obtener_lote_o_404(db: Session, id_lote: str):
    batch = obtener_lote(db, id_lote)
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    return batch


def _ejecutar_transicion_lote(
    db: Session,
    id_lote: str,
    usuario_actual: UsuarioEnToken,
    fn_accion,
    clave_conteo: str,
    verbo_log: str,
    detalle_mensaje: str,
) -> dict:
    _obtener_lote_o_404(db, id_lote)
    cantidad = fn_accion(db, id_lote)
    logger.info(f"Lote {id_lote} {verbo_log} por {usuario_actual.username}: {cantidad} items")
    return {
        "batch_id": id_lote,
        clave_conteo: cantidad,
        "message": f"Lote {verbo_log}. {cantidad} {detalle_mensaje}",
    }


@router.get(
    "/batch/{id_lote}/status",
    response_model=RespuestaEstadoLote,
    summary="Consultar estado de un lote de operaciones",
)
def endpoint_estado_lote(
    id_lote: str,
    desplazamiento: int = Query(0, ge=0, alias="offset"),
    limite: int = Query(100, ge=1, le=1000, alias="limit"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    batch = _obtener_lote_o_404(db, id_lote)

    st = obtener_estado_lote(db, id_lote)
    items = obtener_items_lote(db, id_lote, desplazamiento, limite)

    return RespuestaEstadoLote(
        batch_id=batch.id_lote,
        entity_type=batch.tipo_entidad,
        action=batch.accion,
        total=st["total"],
        pending=st["pending"],
        processing=st["processing"],
        paused=st["paused"],
        completed=st["completed"],
        failed=st["failed"],
        cancelled=st["cancelled"],
        modalidad=batch.modalidad,
        created_at=batch.creado_en,
        completed_at=batch.completado_en,
        offset=desplazamiento,
        limit=limite,
        details=[
            ItemOperacionSalida(
                identifier=i.identificador,
                status=i.estado,
                error_message=i.mensaje_error,
                attempt=i.intento,
            )
            for i in items
        ],
    )


@router.post(
    "/batch/{id_lote}/pause",
    response_model=RespuestaPausaLote,
    summary="Pausar un lote de operaciones",
)
def endpoint_pausar_lote(
    id_lote: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return _ejecutar_transicion_lote(
        db,
        id_lote,
        usuario_actual,
        pausar_lote,
        "paused",
        "pausado",
        "items pendientes marcados como pausados.",
    )


@router.post(
    "/batch/{id_lote}/resume",
    response_model=RespuestaReanudacionLote,
    summary="Reanudar un lote de operaciones pausado",
)
def endpoint_reanudar_lote(
    id_lote: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return _ejecutar_transicion_lote(
        db,
        id_lote,
        usuario_actual,
        reanudar_lote,
        "resumed",
        "reanudado",
        "items vueltos a pendientes.",
    )


@router.post(
    "/batch/{id_lote}/cancel",
    response_model=RespuestaCancelacionLote,
    summary="Cancelar un lote de operaciones",
)
def endpoint_cancelar_lote(
    id_lote: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return _ejecutar_transicion_lote(
        db,
        id_lote,
        usuario_actual,
        cancelar_lote,
        "cancelled",
        "cancelado",
        "items marcados como cancelados.",
    )


@router.delete(
    "/batch/{id_lote}",
    response_model=RespuestaAccionLote,
    summary="Eliminar un lote de operaciones",
)
def endpoint_eliminar_lote(
    id_lote: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    _obtener_lote_o_404(db, id_lote)
    if not eliminar_lote(db, id_lote):
        raise HTTPException(status_code=500, detail="No se pudo eliminar el lote")
    logger.info(f"Lote {id_lote} eliminado por {usuario_actual.username}")
    return {"batch_id": id_lote, "message": "Lote eliminado correctamente."}


@router.get(
    "/batch/{id_lote}/reports",
    response_model=RespuestaListaReportesLote,
    summary="Listar reportes individuales de un lote",
)
def endpoint_listar_reportes_lote(
    id_lote: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    _obtener_lote_o_404(db, id_lote)
    return {"batch_id": id_lote, "reports": listar_reportes_lote(id_lote)}


@router.get("/batch/{id_lote}/reports/download", summary="Descargar reportes (ZIP con CSVs)")
def descargar_reportes_lote(
    id_lote: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    batch = _obtener_lote_o_404(db, id_lote)

    items = obtener_todos_items_lote(db, id_lote)
    guardar_reportes_lote(batch, items)
    zip_path = os.path.join(settings.REPORT_DIR, "batch", f"{id_lote}.zip")
    if not os.path.exists(zip_path):
        zip_path, zip_filename = construir_zip_reportes_lote(batch, items)
        background_tasks.add_task(os.unlink, zip_path)
        return FileResponse(path=zip_path, media_type="application/zip", filename=zip_filename)
    return FileResponse(
        path=zip_path,
        media_type="application/zip",
        filename=f"reportes_{batch.accion}_{batch.tipo_entidad}_{id_lote[:8]}.zip",
    )


@router.get(
    "/batch/{id_lote}/reports/{nombre_reporte}", summary="Descargar un CSV individual de un lote"
)
def descargar_reporte_lote(
    id_lote: str,
    nombre_reporte: str,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    _obtener_lote_o_404(db, id_lote)

    path = obtener_ruta_reporte_lote(id_lote, nombre_reporte)
    if not path:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")
    return FileResponse(path=path, media_type="text/csv", filename=f"{nombre_reporte}.csv")
