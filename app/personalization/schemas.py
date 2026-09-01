from datetime import datetime

from pydantic import BaseModel


class ProfileUpdate(BaseModel):
    prefers_name: str | None = None
    experience_level: str | None = None
    learning_pace: str | None = None
    interests: list[str] | None = None
    custom_notes: str | None = None


class ProfileResponse(BaseModel):
    user_id: int
    prefers_name: str | None
    experience_level: str
    learning_pace: str
    interests: list[str]
    custom_notes: str | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}
