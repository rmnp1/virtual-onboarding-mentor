from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

DEFAULT_EXPERIENCE_LEVEL = "junior"
DEFAULT_LEARNING_PACE = "normal"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    prefers_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    experience_level: Mapped[str] = mapped_column(String(10), default=DEFAULT_EXPERIENCE_LEVEL)
    learning_pace: Mapped[str] = mapped_column(String(10), default=DEFAULT_LEARNING_PACE)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    custom_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
