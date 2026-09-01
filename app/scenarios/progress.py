from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.scenario_progress import ScenarioProgress


def get_or_create_progress(db: Session, user_id: int, scenario_id: str) -> ScenarioProgress:
    progress = (
        db.query(ScenarioProgress)
        .filter(
            ScenarioProgress.user_id == user_id,
            ScenarioProgress.scenario_id == scenario_id,
        )
        .first()
    )
    if progress is None:
        progress = ScenarioProgress(
            user_id=user_id,
            scenario_id=scenario_id,
            status="in_progress",
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress


def update_progress(db: Session, progress: ScenarioProgress, completed: bool = False) -> None:
    if completed:
        progress.status = "completed"
        progress.completed = True
        progress.completed_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(progress)


def list_progress(db: Session, user_id: int) -> list[ScenarioProgress]:
    return db.query(ScenarioProgress).filter(ScenarioProgress.user_id == user_id).all()
