from app.metrics.service import quiz_count
from app.models.scenario_progress import ScenarioProgress
from app.scenarios.engine import get_current_step, process_answer
from app.scenarios.registry import Scenario, Step, get_scenario, load_scenarios


def _welcome_progress() -> ScenarioProgress:
    return ScenarioProgress(user_id=1, scenario_id="welcome")


def test_registry_loads_all_scenarios() -> None:
    scenarios = load_scenarios()
    assert len(scenarios) == 3
    for scenario in scenarios:
        assert scenario.title["en"]
        assert scenario.title["pl"]
        assert scenario.steps


def test_registry_ids_and_roles() -> None:
    assert sorted(s.id for s in load_scenarios()) == ["day1", "role_engineering", "welcome"]
    welcome = get_scenario("welcome")
    assert welcome is not None
    assert "employee" in welcome.roles
    engineering = get_scenario("role_engineering")
    assert engineering is not None
    assert engineering.roles == ["engineering"]


def test_quiz_counts() -> None:
    assert quiz_count(get_scenario("welcome")) == 1
    assert quiz_count(get_scenario("day1")) == 2
    assert quiz_count(get_scenario("role_engineering")) == 2


def test_engine_full_playthrough_completes() -> None:
    scenario = get_scenario("welcome")
    progress = _welcome_progress()
    result = None
    for _ in range(10):
        if result is not None and result.completed:
            break
        step = get_current_step(scenario, progress)
        result = process_answer(scenario, progress, "en", step.answer)

    assert result is not None
    assert result.completed
    assert progress.completed
    assert progress.status == "completed"
    assert progress.score == 1
    assert "completed the welcome scenario" in result.message


def test_engine_wrong_answer_retries() -> None:
    scenario = get_scenario("welcome")
    progress = _welcome_progress()

    result = process_answer(scenario, progress, "en", None)
    assert not result.completed
    assert get_current_step(scenario, progress).id == "mission"

    result = process_answer(scenario, progress, "en", None)
    assert not result.completed
    assert get_current_step(scenario, progress).id == "values_quiz"

    result = process_answer(scenario, progress, "en", 1)
    assert result.correct is False
    assert progress.score is None
    assert get_current_step(scenario, progress).id == "greeting"


def test_engine_completion_fallback() -> None:
    scenario = Scenario(
        id="minimal",
        title={"en": "Minimal", "pl": "Minimal"},
        order=99,
        roles=["employee"],
        steps={
            "s1": Step(
                id="s1",
                type="text",
                content={"en": "hi", "pl": "czesc"},
                next={"en": "", "pl": ""},
            ),
        },
    )
    progress = ScenarioProgress(user_id=1, scenario_id="minimal")
    result = process_answer(scenario, progress, "en", None)
    assert result.completed
    assert "Congratulations!" in result.message


def test_list_scenarios_by_role_auth(auth_headers, client) -> None:
    employee_ids = [s["id"] for s in client.get("/api/scenarios", headers=auth_headers()).json()]
    assert employee_ids == ["welcome", "day1"]

    engineering_ids = [
        s["id"] for s in client.get("/api/scenarios", headers=auth_headers("engineering")).json()
    ]
    assert engineering_ids == ["welcome", "day1", "role_engineering"]


def test_detail_unknown_scenario(client, auth_headers) -> None:
    response = client.get("/api/scenarios/nope", headers=auth_headers())
    assert response.status_code == 404


def test_detail_forbidden_role(client, auth_headers) -> None:
    response = client.get("/api/scenarios/role_engineering", headers=auth_headers())
    assert response.status_code == 403


def test_scenarios_require_auth(client) -> None:
    assert client.get("/api/scenarios").status_code == 401


def test_play_through_welcome_via_api(client, auth_headers, complete_scenario) -> None:
    headers = auth_headers("employee", full_name="Ann")
    detail = client.get("/api/scenarios/welcome", headers=headers).json()
    assert "Ann" in detail["content"]

    result = complete_scenario("welcome", headers)
    assert result["completed"]

    metrics = client.get("/api/metrics/me", headers=headers).json()
    welcome = next(item for item in metrics["scenarios"] if item["scenario_id"] == "welcome")
    assert welcome["status"] == "completed"
    assert welcome["score"] == 1
    assert welcome["score_percent"] == 100.0
