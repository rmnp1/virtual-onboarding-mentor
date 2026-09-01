import pytest

from app.metrics.service import normalize, quiz_count
from app.scenarios.registry import get_scenario


def test_quiz_counts() -> None:
    assert quiz_count(get_scenario("welcome")) == 1
    assert quiz_count(get_scenario("day1")) == 2


def test_normalize() -> None:
    assert normalize(None, 2) is None
    assert normalize(3, 0) is None
    assert normalize(3, 1) == 100.0
    assert normalize(2, 4) == 50.0
    assert normalize(1, 3) == 33.3


def test_me_empty_state(client, auth_headers) -> None:
    headers = auth_headers()
    body = client.get("/api/metrics/me", headers=headers).json()
    assert body["scenarios_total"] == 2
    assert body["scenarios_completed"] == 0
    assert body["progress_percent"] == 0.0
    assert body["avg_score_percent"] is None
    assert body["avg_rating"] is None
    assert {item["status"] for item in body["scenarios"]} == {"not_started"}
    assert all(item["score_percent"] is None for item in body["scenarios"])


def test_me_after_completion(client, auth_headers, complete_scenario) -> None:
    headers = auth_headers()
    complete_scenario("welcome", headers)

    body = client.get("/api/metrics/me", headers=headers).json()
    assert body["scenarios_completed"] == 1
    assert body["progress_percent"] == 50.0
    assert body["avg_score_percent"] == 100.0

    welcome = next(item for item in body["scenarios"] if item["scenario_id"] == "welcome")
    assert welcome["status"] == "completed"
    assert welcome["score"] == 1
    assert welcome["total_quizzes"] == 1
    assert welcome["score_percent"] == 100.0
    assert welcome["completed_at"] is not None
    assert welcome["started_at"] is not None


def test_me_avg_rating(client, auth_headers) -> None:
    headers = auth_headers()
    client.post("/api/feedback", headers=headers, json={"rating": 4})
    client.post("/api/feedback", headers=headers, json={"rating": 2})
    body = client.get("/api/metrics/me", headers=headers).json()
    assert body["avg_rating"] == 3.0


def test_overview_forbidden_for_employee(client, auth_headers) -> None:
    response = client.get("/api/metrics/overview", headers=auth_headers())
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["hr", "mentor", "admin"])
def test_overview_allowed_for_staff(client, auth_headers, role: str) -> None:
    response = client.get("/api/metrics/overview", headers=auth_headers(role))
    assert response.status_code == 200


def test_overview_content(client, auth_headers) -> None:
    admin = auth_headers("admin")
    employee = auth_headers("employee")
    client.post("/api/feedback", headers=employee, json={"rating": 5})

    body = client.get("/api/metrics/overview", headers=admin).json()
    assert body["total_users"] >= 2
    assert body["active_users"] >= 2
    assert body["feedback_total"] >= 1
    assert body["avg_rating"] is not None
    assert 1.0 <= body["avg_rating"] <= 5.0
    assert len(body["scenario_stats"]) == 3
    departments = {entry["department"] for entry in body["users_by_department"]}
    assert "unspecified" in departments
