from dataclasses import dataclass

from app.models.scenario_progress import ScenarioProgress
from app.scenarios.registry import Scenario, Step


@dataclass
class EngineResult:
    message: str
    step_id: str
    completed: bool
    correct: bool | None = None


def get_first_step(scenario: Scenario) -> Step:
    return next(iter(scenario.steps.values()))


def get_current_step(scenario: Scenario, progress: ScenarioProgress) -> Step:
    if progress.current_step:
        step = scenario.steps.get(progress.current_step)
        if step:
            return step
    return get_first_step(scenario)


def _format_step(step: Step, language: str) -> str:
    if step.type == "quiz":
        options = step.options.get(language, [])
        lines = [step.content.get(language, "")]
        for i, opt in enumerate(options):
            lines.append(f"{i}. {opt}")
        return "\n".join(lines)
    return step.content.get(language, "")


def process_answer(
    scenario: Scenario,
    progress: ScenarioProgress,
    language: str,
    answer: int | None,
) -> EngineResult:
    step = get_current_step(scenario, progress)

    if step.type == "quiz":
        if step.answer is not None and answer == step.answer:
            if progress.score is None:
                progress.score = 0
            progress.score += 1
            next_id = step.next.get(language, "")
            return _advance(scenario, progress, language, next_id, correct=True)
        retry_id = step.retry.get(language, "")
        if retry_id and retry_id in scenario.steps:
            retry_step = scenario.steps[retry_id]
            progress.current_step = retry_step.id
            return EngineResult(
                message=_format_step(retry_step, language),
                step_id=retry_step.id,
                completed=False,
                correct=False,
            )
        return EngineResult(
            message=_format_step(step, language),
            step_id=step.id,
            completed=False,
            correct=False,
        )

    next_id = step.next.get(language, "")
    return _advance(scenario, progress, language, next_id, correct=None)


def _advance(
    scenario: Scenario,
    progress: ScenarioProgress,
    language: str,
    next_id: str,
    correct: bool | None,
) -> EngineResult:
    if not next_id or next_id not in scenario.steps:
        progress.current_step = ""
        progress.completed = True
        progress.status = "completed"
        return EngineResult(
            message=_format_step(get_current_step(scenario, progress), language),
            step_id="",
            completed=True,
            correct=correct,
        )

    next_step = scenario.steps[next_id]
    progress.current_step = next_step.id
    if progress.status != "completed":
        progress.status = "in_progress"
    return EngineResult(
        message=_format_step(next_step, language),
        step_id=next_step.id,
        completed=False,
        correct=correct,
    )
