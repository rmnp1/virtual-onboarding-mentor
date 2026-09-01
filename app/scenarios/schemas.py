from pydantic import BaseModel


class ScenarioSummary(BaseModel):
    id: str
    title: str
    order: int
    completed: bool


class ScenarioDetail(BaseModel):
    scenario_id: str
    step_id: str
    type: str
    content: str
    options: list[str] | None = None
    completed: bool


class AnswerRequest(BaseModel):
    answer: int | None = None


class AnswerResponse(BaseModel):
    step_id: str
    message: str
    options: list[str] | None = None
    completed: bool
    correct: bool | None = None
