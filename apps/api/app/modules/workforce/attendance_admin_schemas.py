from pydantic import BaseModel, Field


class AttendanceReopenRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)
