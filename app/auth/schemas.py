from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

MAX_PASSWORD_CHARS = 72
MAX_PASSWORD_BYTES = 72


def _password_bytes_validator(value: str) -> str:
    if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("password must fit within 72 bytes in UTF-8")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_CHARS)
    full_name: str | None = None
    department: str | None = None
    language: Literal["pl", "en"] | None = None

    model_config = {"extra": "forbid"}

    _validate_password_bytes = field_validator("password")(_password_bytes_validator)


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
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_CHARS)

    _validate_password_bytes = field_validator("password")(_password_bytes_validator)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int
