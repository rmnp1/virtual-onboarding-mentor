from datetime import datetime

from pydantic import BaseModel


class ScenarioMetricsItem(BaseModel):
    scenario_id: str
    title: str
    status: str
    score: int | None
    total_quizzes: int
    score_percent: float | None
    started_at: datetime | None
    completed_at: datetime | None


class UserMetricsResponse(BaseModel):
    scenarios_total: int
    scenarios_completed: int
    progress_percent: float
    avg_score_percent: float | None
    avg_rating: float | None
    scenarios: list[ScenarioMetricsItem]


class DepartmentCount(BaseModel):
    department: str
    count: int


class ScenarioStat(BaseModel):
    scenario_id: str
    started_users: int
    completed_users: int
    completion_rate_percent: float
    avg_score_percent: float | None
    feedback_count: int
    avg_rating: float | None


class AdminMetricsResponse(BaseModel):
    total_users: int
    active_users: int
    new_users_30d: int
    users_by_department: list[DepartmentCount]
    scenario_stats: list[ScenarioStat]
    avg_rating: float | None
    feedback_total: int
