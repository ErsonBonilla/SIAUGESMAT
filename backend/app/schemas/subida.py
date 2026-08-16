from pydantic import BaseModel


class UploadResponse(BaseModel):
    execution_id: int
    filename: str
    semester: str
    mode: str
    status: str
    message: str


class SemesterResponse(BaseModel):
    semester: str
