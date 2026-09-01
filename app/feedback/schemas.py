from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    scenario_id: str | None = None
    comment: str | None = None


class FeedbackResponse(BaseModel):
    id: int
    scenario_id: str | None
    rating: int
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
