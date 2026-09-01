from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.feedback.schemas import FeedbackCreate
from app.models.feedback import Feedback
from app.models.user import User
from app.scenarios.registry import get_scenario


def create_feedback(db: Session, user: User, body: FeedbackCreate) -> Feedback:
    if body.scenario_id is not None and get_scenario(body.scenario_id) is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    feedback = Feedback(
        user_id=user.id,
        scenario_id=body.scenario_id,
        rating=body.rating,
        comment=body.comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_user_feedback(db: Session, user: User) -> list[Feedback]:
    return (
        db.query(Feedback)
        .filter(Feedback.user_id == user.id)
        .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .all()
    )
