import os
import tempfile
from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

_TMP_DIR = tempfile.mkdtemp(prefix="vom_tests_")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"
os.environ["CHROMA_PERSIST_DIR"] = f"{_TMP_DIR}/chroma"

from app.chat.routes import chat_history  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base, engine, init_db  # noqa: E402
from app.scenarios.registry import get_scenario  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_schema() -> Iterator[None]:
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def _clear_chat_history() -> Iterator[None]:
    chat_history.clear()
    yield
    chat_history.clear()


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def user_factory(client: TestClient):
    def _factory(
        role: str = "employee",
        language: str = "en",
        **overrides: object,
    ) -> dict[str, object]:
        email = f"{uuid4().hex}@example.com"
        password = "password1"
        payload: dict[str, object] = {
            "email": email,
            "password": password,
            "role": role,
            "language": language,
        }
        payload.update(overrides)

        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 201, response.text
        user_id = int(response.json()["id"])

        login = client.post("/api/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200, login.text
        token = str(login.json()["access_token"])
        return {
            "id": user_id,
            "email": email,
            "password": password,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
        }

    return _factory


@pytest.fixture()
def auth_token(user_factory):
    def _token(role: str = "employee", **overrides: object) -> str:
        user = user_factory(role=role, **overrides)
        return str(user["token"])

    return _token


@pytest.fixture()
def auth_headers(user_factory):
    def _headers(role: str = "employee", **overrides: object) -> dict[str, str]:
        user = user_factory(role=role, **overrides)
        return dict(user["headers"])

    return _headers


@pytest.fixture()
def complete_scenario(client: TestClient):
    def _complete(scenario_id: str, headers: dict[str, str]) -> dict[str, object]:
        result = client.get(f"/api/scenarios/{scenario_id}", headers=headers).json()
        for _ in range(20):
            if result["completed"]:
                return result
            step = get_scenario(scenario_id).steps[result["step_id"]]
            answer = step.answer if result["options"] else None
            response = client.post(
                f"/api/scenarios/{scenario_id}/answer",
                headers=headers,
                json={"answer": answer},
            )
            assert response.status_code == 200, response.text
            result = response.json()
        raise AssertionError(f"Scenario {scenario_id} did not complete")

    return _complete


DEFAULT_CHUNK = {
    "text": "Employees work from home on Fridays.",
    "source": "policies.md",
    "language": "en",
    "score": 0.2,
}


@pytest.fixture()
def patch_search(monkeypatch):
    def _apply(chunks: list[dict[str, object]] | None = None) -> None:
        selected = chunks if chunks is not None else [dict(DEFAULT_CHUNK)]
        monkeypatch.setattr(
            "app.chat.context.search",
            lambda *args, **kwargs: selected,
        )

    return _apply


@pytest.fixture()
def patch_generate(monkeypatch):
    def _apply(reply: str = "Hello there!") -> None:
        monkeypatch.setattr("app.chat.routes.generate", lambda *args, **kwargs: reply)

    return _apply


@pytest.fixture()
def patch_generate_stream(monkeypatch):
    def _apply(
        tokens: list[str] | None = None,
        exc: Exception | None = None,
    ) -> None:
        selected = tokens if tokens is not None else ["Hel", "lo ", "world"]

        def stream(*args: object, **kwargs: object):
            if exc is not None:
                raise exc
            yield from selected

        monkeypatch.setattr("app.chat.routes.generate_stream", stream)

    return _apply
