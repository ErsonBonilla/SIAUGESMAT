import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import obtener_db, obtener_usuario_actual
from app.repositories.repositorio_operaciones import (
    listar_lotes,
    obtener_analitica_operaciones,
    obtener_conteos_pausados_lote,
)
from app.schemas.operaciones import (
    LoteSalidaLista,
    MetricasMensualesOperacion,
    RespuestaAnaliticaOperaciones,
    RespuestaListaLotes,
)
from app.schemas.usuario import UsuarioEnToken

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/batches", response_model=RespuestaListaLotes, summary="Listar lotes de operaciones")
def listar_lotes_operacion(
    tipo_entidad: str | None = Query(
        None, alias="entity_type", description="courses, categories, users"
    ),
    accion: str | None = Query(None, alias="action", description="create, delete"),
    modalidad: str | None = Query(None),
    limite: int = Query(20, ge=1, le=100, alias="limit"),
    desplazamiento: int = Query(0, ge=0, alias="offset"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    total, batches = listar_lotes(
        db,
        tipo_entidad=tipo_entidad,
        accion=accion,
        modalidad=modalidad,
        limit=limite,
        offset=desplazamiento,
    )
    batch_ids = [b.id_lote for b in batches]
    paused_counts = obtener_conteos_pausados_lote(db, batch_ids)
    items = []
    for b in batches:
        item = LoteSalidaLista.model_validate(b)
        item.pausados = paused_counts.get(b.id_lote, 0)
        items.append(item)
    return RespuestaListaLotes(total=total, items=items)


@router.get(
    "/analytics",
    response_model=RespuestaAnaliticaOperaciones,
    summary="Analítica histórica de operaciones masivas",
)
def obtener_historial_operaciones(
    modalidad: str | None = Query(None),
    meses: int = Query(12, ge=1, le=60, alias="months"),
    tipo_entidad: str | None = Query(
        None, alias="entity_type", description="courses, categories, users"
    ),
    accion: str | None = Query(None, alias="action", description="create, delete"),
    db: Session = Depends(obtener_db),
    usuario_actual: UsuarioEnToken = Depends(obtener_usuario_actual),
):
    history = obtener_analitica_operaciones(
        db,
        modalidad=modalidad,
        months=meses,
        tipo_entidad=tipo_entidad,
        accion=accion,
    )
    return RespuestaAnaliticaOperaciones(
        history=[MetricasMensualesOperacion(**m) for m in history],
    )
