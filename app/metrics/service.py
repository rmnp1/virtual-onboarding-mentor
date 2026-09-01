from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.metrics.schemas import (
    AdminMetricsResponse,
    DepartmentCount,
    ScenarioMetricsItem,
    ScenarioStat,
    UserMetricsResponse,
)
from app.models.feedback import Feedback
from app.models.scenario_progress import ScenarioProgress
from app.models.user import User
from app.scenarios.registry import Scenario, get_scenarios_for_role, load_scenarios


def quiz_count(scenario: Scenario) -> int:
    return sum(1 for step in scenario.steps.values() if step.answer is not None)


def normalize(score: int | None, total: int) -> float | None:
    if total <= 0 or score is None:
        return None
    return round(min(100.0, score / total * 100.0), 1)


def _rounded_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100.0, 1)


def _optional_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def user_metrics(db: Session, user: User) -> UserMetricsResponse:
    scenarios = get_scenarios_for_role(user.role)
    progress_rows = {
        p.scenario_id: p
        for p in db.query(ScenarioProgress).filter(ScenarioProgress.user_id == user.id).all()
    }

    items: list[ScenarioMetricsItem] = []
    for scenario in scenarios:
        progress = progress_rows.get(scenario.id)
        total = quiz_count(scenario)
        score = progress.score if progress else None
        items.append(
            ScenarioMetricsItem(
                scenario_id=scenario.id,
                title=scenario.title.get(user.language, scenario.title["en"]),
                status=progress.status if progress else "not_started",
                score=score,
                total_quizzes=total,
                score_percent=normalize(score, total),
                started_at=progress.started_at if progress else None,
                completed_at=progress.completed_at if progress else None,
            )
        )

    completed = [item for item in items if item.status == "completed"]
    score_percents = [item.score_percent for item in completed if item.score_percent is not None]
    rating = db.query(func.avg(Feedback.rating)).filter(Feedback.user_id == user.id).scalar()

    return UserMetricsResponse(
        scenarios_total=len(items),
        scenarios_completed=len(completed),
        progress_percent=_rounded_percent(len(completed), len(items)),
        avg_score_percent=_avg([float(p) for p in score_percents]),
        avg_rating=_optional_float(rating),
        scenarios=items,
    )


def admin_metrics(db: Session) -> AdminMetricsResponse:
    total_users = int(db.query(func.count(User.id)).scalar() or 0)
    active_users = int(db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0)
    cutoff = datetime.now(UTC) - timedelta(days=30)
    new_users_30d = int(
        db.query(func.count(User.id)).filter(User.created_at >= cutoff).scalar() or 0
    )

    dept_rows = db.query(User.department, func.count(User.id)).group_by(User.department).all()
    users_by_department = [
        DepartmentCount(department=department or "unspecified", count=int(count))
        for department, count in dept_rows
    ]
    users_by_department.sort(key=lambda d: d.count, reverse=True)

    scenario_stats: list[ScenarioStat] = []
    for scenario in load_scenarios():
        total = quiz_count(scenario)
        started = int(
            db.query(func.count(ScenarioProgress.id))
            .filter(ScenarioProgress.scenario_id == scenario.id)
            .scalar()
            or 0
        )
        completed = int(
            db.query(func.count(ScenarioProgress.id))
            .filter(
                ScenarioProgress.scenario_id == scenario.id,
                ScenarioProgress.completed.is_(True),
            )
            .scalar()
            or 0
        )
        score_rows = (
            db.query(ScenarioProgress.score)
            .filter(
                ScenarioProgress.scenario_id == scenario.id,
                ScenarioProgress.completed.is_(True),
                ScenarioProgress.score.isnot(None),
            )
            .all()
        )
        score_percents: list[float] = []
        for (value,) in score_rows:
            pct = normalize(value, total)
            if pct is not None:
                score_percents.append(pct)

        feedback_count = int(
            db.query(func.count(Feedback.id)).filter(Feedback.scenario_id == scenario.id).scalar()
            or 0
        )
        feedback_avg = (
            db.query(func.avg(Feedback.rating)).filter(Feedback.scenario_id == scenario.id).scalar()
        )
        scenario_stats.append(
            ScenarioStat(
                scenario_id=scenario.id,
                started_users=started,
                completed_users=completed,
                completion_rate_percent=_rounded_percent(completed, started),
                avg_score_percent=_avg(score_percents),
                feedback_count=feedback_count,
                avg_rating=_optional_float(feedback_avg),
            )
        )

    all_feedback_avg = db.query(func.avg(Feedback.rating)).scalar()
    feedback_total = int(db.query(func.count(Feedback.id)).scalar() or 0)

    return AdminMetricsResponse(
        total_users=total_users,
        active_users=active_users,
        new_users_30d=new_users_30d,
        users_by_department=users_by_department,
        scenario_stats=scenario_stats,
        avg_rating=_optional_float(all_feedback_avg),
        feedback_total=feedback_total,
    )
