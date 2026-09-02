from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.dependencies import create_access_token, get_current_user
from app.auth.password import hash_password, verify_password
from app.auth.ratelimit import (
    check_rate_limit,
    ip_enforce,
    login_email,
    login_ip,
    register_ip,
)
from app.auth.schemas import LoginRequest, TokenResponse, UserCreate, UserResponse
from app.config import settings
from app.models.base import get_db
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def auth_config() -> dict[str, bool]:
    return {"invite_required": settings.invite_required}


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, request: Request, db: Session = Depends(get_db)) -> User:
    ip_enforce(register_ip, request)
    if settings.invite_required:
        codes = [c.strip().lower() for c in settings.invite_codes.split(",") if c.strip()]
        if not body.invite_code or body.invite_code.strip().lower() not in codes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Valid invite code required",
            )
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        department=body.department,
        role="employee",
        language=body.language or "pl",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    ip_enforce(login_ip, request)
    check_rate_limit(login_email, body.email.lower())
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
