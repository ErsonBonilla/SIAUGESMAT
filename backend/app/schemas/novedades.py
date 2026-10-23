from pydantic import BaseModel, ConfigDict, Field


class ItemNovedad(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    clave_base: str = Field(alias="base_key")
    shortname_anterior: str = Field(alias="old_shortname")
    shortname_nuevo: str = Field(alias="new_shortname")
    cedula_prof_anterior: str | None = Field(default=None, alias="old_prof_cedula")
    cedula_prof_nuevo: str | None = Field(default=None, alias="new_prof_cedula")
    nombre_prof_anterior: str = Field(default="", alias="old_prof_name")
    nombre_prof_nuevo: str = Field(default="", alias="new_prof_name")
    nombre_completo_curso: str = Field(default="", alias="course_fullname")
    accion: str = Field(default="", alias="action")
    id_curso_destino: int | None = Field(default=None, alias="target_course_id")


class RespuestaNovedades(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    semestre: str = Field(alias="semester")
    ejecucion_anterior_id: int = Field(alias="previous_execution_id")
    nombre_archivo_anterior: str = Field(alias="previous_filename")
    total_comparados: int = Field(alias="total_compared")
    novedades: list[ItemNovedad]
