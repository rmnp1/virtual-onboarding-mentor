from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    department: str | None = None
    language: Literal["pl", "en"] | None = None

    model_config = {"extra": "forbid"}


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    role: str
    language: str
    department: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
