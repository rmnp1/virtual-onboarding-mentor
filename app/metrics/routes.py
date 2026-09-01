from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.metrics.schemas import AdminMetricsResponse, UserMetricsResponse
from app.metrics.service import admin_metrics, user_metrics
from app.models.base import get_db
from app.models.user import User

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/me", response_model=UserMetricsResponse)
def my_metrics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserMetricsResponse:
    return user_metrics(db, user)


@router.get("/overview", response_model=AdminMetricsResponse)
def overview(
    user: User = Depends(require_role("admin", "hr", "mentor")),
    db: Session = Depends(get_db),
) -> AdminMetricsResponse:
    return admin_metrics(db)
