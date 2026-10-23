from pydantic import BaseModel, ConfigDict, Field


class RespuestaSubida(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    ejecucion_id: int = Field(alias="execution_id")
    nombre_archivo: str = Field(alias="filename")
    semestre: str = Field(alias="semester")
    modo: str = Field(alias="mode")
    estado: str = Field(alias="status")
    mensaje: str = Field(alias="message")


class RespuestaSemestre(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    semestre: str = Field(alias="semester")
