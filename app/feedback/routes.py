from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.feedback.schemas import FeedbackCreate, FeedbackResponse
from app.feedback.service import create_feedback, list_user_feedback
from app.models.base import get_db
from app.models.user import User

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def add_feedback(
    body: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    return FeedbackResponse.model_validate(create_feedback(db, user, body))


@router.get("", response_model=list[FeedbackResponse])
def get_feedback(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[FeedbackResponse]:
    return [FeedbackResponse.model_validate(f) for f in list_user_feedback(db, user)]
