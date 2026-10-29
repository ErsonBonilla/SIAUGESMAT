"""
Endpoints de gestión de ejecuciones (jobs) del proceso ETL.
"""

import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import settings
from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.repositories.repositorio_ejecuciones import (
    cancelar_ejecucion,
    eliminar_ejecucion,
    listar_ejecuciones,
    marcar_en_cola_atomicamente,
    obtener_ejecucion,
    obtener_ejecucion_activa,
    obtener_errores_ejecucion,
    pausar_ejecucion,
)
from app.repositories.repositorio_operaciones import obtener_lote_activo
from app.schemas.trabajo import (
    EjecucionSalida,
    ErrorSalida,
    ListaEjecuciones,
    RespuestaProceso,
)
from app.schemas.usuario import UsuarioEnToken
from app.services.orquestacion import encolar_etl, revocar_tarea

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolver_ejecucion(
    db: Session, ejecucion_id: int, expected_statuses=None, conflict_message=None
):
    """Obtiene una ejecución y valida que exista y esté en el estado esperado."""
    execution = obtener_ejecucion(db, ejecucion_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ejecución no encontrada."
        )
    if expected_statuses and execution.estado not in expected_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_message
            or (
                f"La ejecución está en estado '{execution.estado}'"
                f" y no puede ser procesada nuevamente."
            ),
        )
    return execution


@router.post(
    "/{ejecucion_id}/process",
    response_model=RespuestaProceso,
    summary="Iniciar el procesamiento ETL de una ejecución",
    status_code=status.HTTP_202_ACCEPTED,
)
async def iniciar_proceso(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    execution = _resolver_ejecucion(
        db,
        ejecucion_id,
        expected_statuses={"pending", "failed", "queued", "review_required", "paused"},
    )

    if execution.modalidad == "PRESENCIAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se puede procesar una ejecución de modalidad PRESENCIAL.",
        )

    if obtener_ejecucion_activa(
        db, execution.modalidad, exclude_id=ejecucion_id
    ) or obtener_lote_activo(db, execution.modalidad):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proceso en ejecución en esta modalidad. "
            "Espere a que finalice antes de iniciar otro.",
        )

    file_path = os.path.join(settings.UPLOAD_DIR, execution.nombre_archivo)
    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo asociado a la ejecución no se encuentra en el servidor.",
        )

    try:
        job = encolar_etl(ejecucion_id, file_path, execution.semestre)
    except Exception:
        logger.exception("Error al encolar la tarea ETL")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo encolar la tarea de procesamiento.",
        ) from None

        # Atomic: check status + update + save task_id en un solo UPDATE
    ALLOWED = ("pending", "failed", "queued", "review_required", "paused")
    if not marcar_en_cola_atomicamente(db, ejecucion_id, job.id, ALLOWED):
        # Otro request ya ganó la carrera — revocar task y responder 409
        revocar_tarea(job.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La ejecución ya fue procesada por otra solicitud concurrente.",
        )

    logger.info(
        f"Tarea encolada para ejecución {ejecucion_id}: task_id={job.id} "
        f"por {usuario_actual.username} (modo={execution.modo})"
    )

    return RespuestaProceso(
        execution_id=ejecucion_id,
        job_id=job.id,
        status="queued",
        message="Procesamiento encolado correctamente.",
    )


@router.get(
    "/{ejecucion_id}",
    response_model=EjecucionSalida,
    summary="Obtener detalles de una ejecución",
)
async def endpoint_obtener_ejecucion(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    return _resolver_ejecucion(db, ejecucion_id)


@router.get(
    "/{ejecucion_id}/errors",
    response_model=list[ErrorSalida],
    summary="Listar errores de una ejecución",
)
async def endpoint_errores_ejecucion(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
    limite: int = Query(100, ge=1, le=1000, alias="limit"),
    desplazamiento: int = Query(0, ge=0, alias="offset"),
):
    _resolver_ejecucion(db, ejecucion_id)
    return obtener_errores_ejecucion(db, ejecucion_id, limite, desplazamiento)


@router.get(
    "",
    response_model=ListaEjecuciones,
    summary="Listar ejecuciones históricas",
)
async def endpoint_listar_ejecuciones(
    semestre: str | None = Query(None, alias="semester"),
    estado: str | None = Query(None, alias="status"),
    modo: str | None = Query(None, alias="mode"),
    moodle_version: str | None = Query(None),
    modalidad: str | None = Query(None),
    limite: int = Query(20, ge=1, le=100, alias="limit"),
    desplazamiento: int = Query(0, ge=0, alias="offset"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    total, executions = listar_ejecuciones(
        db,
        semestre=semestre,
        estado=estado,
        modo=modo,
        version_moodle=moodle_version,
        modalidad=modalidad,
        limit=limite,
        offset=desplazamiento,
    )
    return ListaEjecuciones(
        total=total,
        items=[EjecucionSalida.model_validate(e) for e in executions],
    )


@router.delete(
    "/{ejecucion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar una ejecución",
)
async def endpoint_eliminar_ejecucion(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    _resolver_ejecucion(
        db,
        ejecucion_id,
        expected_statuses={"pending", "failed", "review_required", "cancelled", "queued"},
    )
    eliminar_ejecucion(db, ejecucion_id)
    logger.info(f"Ejecución {ejecucion_id} eliminada por {usuario_actual.username}")


@router.post(
    "/{ejecucion_id}/confirm",
    response_model=RespuestaProceso,
    summary="Confirmar eliminación masiva de cursos",
    status_code=status.HTTP_202_ACCEPTED,
)
async def confirmar_eliminacion_masiva(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    execution = _resolver_ejecucion(db, ejecucion_id)

    if execution.estado != "review_required":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La ejecución está en estado '{execution.estado}'. "
            f"Solo se puede confirmar ejecuciones en 'review_required'.",
        )

    if execution.modalidad == "PRESENCIAL":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No se puede procesar una ejecución de modalidad PRESENCIAL.",
        )

    if obtener_ejecucion_activa(
        db, execution.modalidad, exclude_id=ejecucion_id
    ) or obtener_lote_activo(db, execution.modalidad):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un proceso en ejecución en esta modalidad. "
            "Espere a que finalice antes de iniciar otro.",
        )

        # 1. Validar archivo PRIMERO
    file_path = os.path.join(settings.UPLOAD_DIR, execution.nombre_archivo)
    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo asociado a la ejecución no se encuentra en el servidor.",
        )

        # 2. Encolar Celery task
    try:
        job = encolar_etl(ejecucion_id, file_path, execution.semestre)
    except Exception:
        logger.exception("Error al encolar la tarea ETL")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo encolar la tarea de procesamiento.",
        ) from None

        # 3. Actualizar DB verificando transición atómica desde review_required
    from app.db.modelos import Ejecucion

    updated = (
        db.query(Ejecucion)
        .filter(Ejecucion.id == ejecucion_id, Ejecucion.estado == "review_required")
        .update(
            {
                Ejecucion.estado: "pending",
                Ejecucion.fase_actual: "Eliminación masiva confirmada",
                Ejecucion.porcentaje_progreso: 30,
                Ejecucion.id_tarea_celery: job.id,
                Ejecucion.iniciado_en: datetime.now(UTC),
            },
            synchronize_session=False,
        )
    )
    if not updated:
        revocar_tarea(job.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La ejecución ya fue confirmada por otra solicitud concurrente.",
        )
    db.expire(execution)
    if execution.checkpoint_fase is None:
        execution.checkpoint_fase = {}
    execution.checkpoint_fase["delete_confirmed"] = True
    flag_modified(execution, "checkpoint_fase")
    db.commit()

    logger.info(
        f"Eliminación masiva confirmada para ejecución {ejecucion_id} por {usuario_actual.username}"
    )

    return RespuestaProceso(
        execution_id=ejecucion_id,
        job_id=job.id,
        status="queued",
        message="Confirmación recibida. Procesamiento reanudado.",
    )


@router.post(
    "/{ejecucion_id}/pause",
    response_model=RespuestaProceso,
    summary="Pausar una ejecución en curso",
    status_code=status.HTTP_202_ACCEPTED,
)
async def endpoint_pausar_ejecucion(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    _resolver_ejecucion(
        db,
        ejecucion_id,
        expected_statuses={"running"},
        conflict_message="Solo se puede pausar ejecuciones en 'running'.",
    )

    success, task_id = pausar_ejecucion(db, ejecucion_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo pausar la ejecución.",
        )

    if task_id:
        revocar_tarea(task_id)
        logger.info(f"Tarea Celery {task_id} revocada para ejecución {ejecucion_id}")

    logger.info(f"Ejecución {ejecucion_id} pausada por {usuario_actual.username}")
    return RespuestaProceso(
        execution_id=ejecucion_id,
        job_id="",
        status="paused",
        message="Ejecución pausada. Usa /process para continuar.",
    )


@router.post(
    "/{ejecucion_id}/cancel",
    response_model=RespuestaProceso,
    summary="Cancelar una ejecución",
    status_code=status.HTTP_202_ACCEPTED,
)
async def endpoint_cancelar_ejecucion(
    ejecucion_id: int,
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    _resolver_ejecucion(
        db,
        ejecucion_id,
        expected_statuses={"running", "paused", "queued"},
        conflict_message=("Solo se puede cancelar ejecuciones en 'running', 'paused' o 'queued'."),
    )

    success, task_id = cancelar_ejecucion(db, ejecucion_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo cancelar la ejecución.",
        )

    if task_id:
        revocar_tarea(task_id)
        logger.info(f"Tarea Celery {task_id} revocada para ejecución {ejecucion_id}")

    logger.info(f"Ejecución {ejecucion_id} cancelada por {usuario_actual.username}")
    return RespuestaProceso(
        execution_id=ejecucion_id,
        job_id=task_id,
        status="cancelled",
        message="Ejecución cancelada.",
    )
