import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.schemas.operations import CsvUploadResponse
from app.schemas.user import UserInToken
from app.api.v1.upload_handler import handle_upload, handle_visibility_upload

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/courses/upload-csv", response_model=CsvUploadResponse, summary="Eliminar cursos masivamente")
async def delete_courses_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await handle_upload(file, db, current_user, entity_type="courses", action="delete")


@router.post("/categories/upload-csv", response_model=CsvUploadResponse, summary="Eliminar categorías masivamente")
async def delete_categories_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await handle_upload(file, db, current_user, entity_type="categories", action="delete")


@router.post("/users/upload-csv", response_model=CsvUploadResponse, summary="Eliminar usuarios masivamente")
async def delete_users_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await handle_upload(file, db, current_user, entity_type="users", action="delete")


@router.post("/courses/visibility", response_model=CsvUploadResponse,
             summary="Cambiar visibilidad de cursos masivamente")
async def bulk_course_visibility(
    file: UploadFile = File(...),
    visibility: str = Query("show", regex="^(show|hide)$"),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await handle_visibility_upload(file, db, current_user, visibility)


@router.post("/users/create-csv", response_model=CsvUploadResponse, summary="Crear usuarios masivamente")
async def create_users_csv(
    file: UploadFile = File(...),
    default_role: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await handle_upload(file, db, current_user, entity_type="users", action="create",
                               default_role=default_role)


@router.post("/categories/create-csv", response_model=CsvUploadResponse, summary="Crear categorías masivamente")
async def create_categories_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: UserInToken = Depends(get_current_user),
):
    return await handle_upload(file, db, current_user, entity_type="categories", action="create")
