import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.repositories.operation_repo import (
    get_batch_paused_counts,
    get_operations_analytics,
    list_batches,
)
from app.schemas.operations import (
    BatchListOut,
    BatchListResponse,
    OperationMonthlyMetrics,
    OperationsAnalyticsResponse,
)
from app.schemas.user import UserInToken

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/batches", response_model=BatchListResponse, summary="Listar lotes de operaciones")
def list_operation_batches(
    entity_type: str | None = Query(None, description="courses, categories, users"),
    action: str | None = Query(None, description="create, delete"),
    modalidad: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    total, batches = list_batches(
        db,
        entity_type=entity_type,
        action=action,
        modalidad=modalidad,
        limit=limit,
        offset=offset,
    )
    batch_ids = [b.batch_id for b in batches]
    paused_counts = get_batch_paused_counts(db, batch_ids)
    items = []
    for b in batches:
        item = BatchListOut.model_validate(b)
        item.paused = paused_counts.get(b.batch_id, 0)
        items.append(item)
    return BatchListResponse(total=total, items=items)


@router.get(
    "/analytics",
    response_model=OperationsAnalyticsResponse,
    summary="Analítica histórica de operaciones masivas",
)
def get_operations_history(
    modalidad: str | None = Query(None),
    months: int = Query(12, ge=1, le=60),
    entity_type: str | None = Query(None, description="courses, categories, users"),
    action: str | None = Query(None, description="create, delete"),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    history = get_operations_analytics(
        db,
        modalidad=modalidad,
        months=months,
        entity_type=entity_type,
        action=action,
    )
    return OperationsAnalyticsResponse(
        history=[OperationMonthlyMetrics(**m) for m in history],
    )
