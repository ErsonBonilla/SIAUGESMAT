from typing import List, Optional

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
    action: str = ""
    target_course_id: Optional[int] = None


class NovedadesResponse(BaseModel):
    semester: str
    previous_execution_id: int
    previous_filename: str
    total_compared: int
    novedades: List[NovedadItem]
