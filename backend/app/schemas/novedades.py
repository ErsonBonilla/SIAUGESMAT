from typing import Dict, List, Optional

from pydantic import BaseModel


class NovedadItem(BaseModel):
    id: str
    base_key: str
    old_shortname: str
    new_shortname: str
    old_prof_cedula: Optional[str] = None
    new_prof_cedula: Optional[str] = None
    old_prof_name: str = ""
    new_prof_name: str = ""
    course_fullname: str = ""
    action: str  # "hide_and_create" | "unhide"
    target_course_id: Optional[int] = None


class NovedadesCompareRequest(BaseModel):
    semester: str
    modalidad: str = "DISTANCIA"


class NovedadesResponse(BaseModel):
    semester: str
    previous_execution_id: int
    previous_filename: str
    total_compared: int
    novedades: List[NovedadItem]


class ApplyNovedadItem(BaseModel):
    id: str
    action: str
    old_shortname: str
    new_shortname: str
    course_fullname: str
    category_idnumber: str = ""
    new_prof_username: str = ""
    new_prof_cedula: str = ""


class ApplyNovedadesRequest(BaseModel):
    semester: str
    novedades: List[ApplyNovedadItem]


class ApplyResult(BaseModel):
    novedad_id: str
    success: bool
    action: str
    message: str = ""


class ApplyNovedadesResponse(BaseModel):
    total: int
    applied: int
    failed: int
    results: List[ApplyResult]
