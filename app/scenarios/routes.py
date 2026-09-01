from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.models.base import get_db
from app.models.scenario_progress import ScenarioProgress
from app.models.user import User
from app.scenarios.engine import process_answer
from app.scenarios.registry import get_scenario, get_scenarios_for_role
from app.scenarios.schemas import (
    AnswerRequest,
    AnswerResponse,
    ScenarioDetail,
    ScenarioSummary,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioSummary])
def list_scenarios(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ScenarioSummary]:
    scenarios = get_scenarios_for_role(user.role)
    progress_rows = {
        p.scenario_id: p
        for p in db.query(ScenarioProgress).filter(ScenarioProgress.user_id == user.id).all()
    }

    result: list[ScenarioSummary] = []
    for scenario in scenarios:
        progress = progress_rows.get(scenario.id)
        result.append(
            ScenarioSummary(
                id=scenario.id,
                title=scenario.title.get(user.language, scenario.title["en"]),
                order=scenario.order,
                completed=progress.completed if progress else False,
            )
        )
    result.sort(key=lambda s: s.order)
    return result


@router.get("/{scenario_id}", response_model=ScenarioDetail)
def scenario_detail(
    scenario_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScenarioDetail:
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if user.role not in scenario.roles:
        raise HTTPException(status_code=403, detail="Scenario not available for your role")

    progress = (
        db.query(ScenarioProgress)
        .filter(
            ScenarioProgress.user_id == user.id,
            ScenarioProgress.scenario_id == scenario_id,
        )
        .first()
    )

    from app.scenarios.engine import get_current_step
    from app.scenarios.progress import get_or_create_progress

    if progress is None or not progress.current_step:
        progress = get_or_create_progress(db, user.id, scenario_id)
    step = get_current_step(scenario, progress)

    language = user.language
    options = step.options.get(language) if step.answer is not None else None
    return ScenarioDetail(
        scenario_id=scenario_id,
        step_id=step.id,
        type=step.type,
        content=step.content.get(language, ""),
        options=options,
        completed=progress.completed,
    )


@router.post("/{scenario_id}/answer", response_model=AnswerResponse)
def scenario_answer(
    scenario_id: str,
    body: AnswerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnswerResponse:
    scenario = get_scenario(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if user.role not in scenario.roles:
        raise HTTPException(status_code=403, detail="Scenario not available for your role")

    from app.scenarios.progress import get_or_create_progress, update_progress

    progress = get_or_create_progress(db, user.id, scenario_id)
    language = user.language

    result = process_answer(scenario, progress, language, body.answer)
    if not result.completed:
        update_progress(db, progress)
    else:
        update_progress(db, progress, completed=True)

    current_step = scenario.steps.get(result.step_id) if result.step_id else None
    options = (
        current_step.options.get(language)
        if current_step and current_step.answer is not None
        else None
    )

    return AnswerResponse(
        step_id=result.step_id,
        message=result.message,
        options=options,
        completed=result.completed,
        correct=result.correct,
    )
