from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.models.base import get_db
from app.models.user import User
from app.models.user_profile import DEFAULT_EXPERIENCE_LEVEL, DEFAULT_LEARNING_PACE, UserProfile
from app.personalization.schemas import ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["profile"])


def _get_or_none(db: Session, user: User) -> UserProfile | None:
    return db.query(UserProfile).filter(UserProfile.user_id == user.id).first()


@router.get("", response_model=ProfileResponse)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = _get_or_none(db, user)
    if profile is None:
        return ProfileResponse(
            user_id=user.id,
            prefers_name=None,
            experience_level=DEFAULT_EXPERIENCE_LEVEL,
            learning_pace=DEFAULT_LEARNING_PACE,
            interests=[],
            custom_notes=None,
            updated_at=None,
        )
    return ProfileResponse.model_validate(profile)


@router.put("", response_model=ProfileResponse)
def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    profile = _get_or_none(db, user)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    payload = body.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return ProfileResponse.model_validate(profile)
