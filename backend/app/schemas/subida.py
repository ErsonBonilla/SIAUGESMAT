from pydantic import BaseModel


class RespuestaSubida(BaseModel):
    execution_id: int
    filename: str
    semester: str
    mode: str
    status: str
    message: str


class RespuestaSemestre(BaseModel):
    semester: str
