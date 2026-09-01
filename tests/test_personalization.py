from app.models.user import User
from app.models.user_profile import UserProfile
from app.personalization.service import (
    build_profile_context,
    build_system_prompt,
    get_display_name,
    personalize_instruction,
    render_content,
)


def _user(**overrides: object) -> User:
    return User(id=1, email="u@test.local", password_hash="hash", **overrides)


def _profile(**overrides: object) -> UserProfile:
    defaults: dict[str, object] = {
        "user_id": 1,
        "experience_level": "junior",
        "learning_pace": "normal",
        "interests": [],
    }
    defaults.update(overrides)
    return UserProfile(**defaults)


def test_display_name_fallback() -> None:
    user = _user()
    assert get_display_name(user, None, "en") == "new colleague"
    assert get_display_name(user, None, "pl") == "nowy kolego"


def test_display_name_priority() -> None:
    user = _user(full_name="Bob")
    profile = _profile(prefers_name="Ann")
    assert get_display_name(user, None, "en") == "Bob"
    assert get_display_name(user, profile, "en") == "Ann"


def test_render_content_tokens() -> None:
    user = _user(full_name="Bob")
    profile = _profile(prefers_name="Ann")
    assert render_content("Hi {name}", user, None, "en") == "Hi Bob"
    assert render_content("Hi {name}", user, profile, "en") == "Hi Ann"


def test_build_profile_context() -> None:
    user = _user(full_name="Bob", role="employee", department="IT")
    profile = _profile(
        experience_level="senior",
        learning_pace="fast",
        interests=["python"],
        custom_notes="prefers async",
    )
    context = build_profile_context(user, profile, "en")
    assert "Name: Bob" in context
    assert "Department: IT" in context
    assert "Experience level: senior" in context
    assert "Interests: python" in context
    assert "Notes: prefers async" in context


def test_personalize_instruction_empty_for_unknown_values() -> None:
    user = _user()
    profile = _profile(experience_level="unknown", learning_pace="unknown")
    assert personalize_instruction(user, profile, "en") == ""


def test_personalize_instruction_for_known_values() -> None:
    user = _user()
    profile = _profile(experience_level="senior", learning_pace="fast")
    instruction = personalize_instruction(user, profile, "en")
    assert "[Personalization]" in instruction
    assert "technical" in instruction
    assert "straight to the point" in instruction


def test_build_system_prompt_base() -> None:
    prompt = build_system_prompt("en", _user(), None)
    assert "virtual onboarding mentor" in prompt
    assert "[User profile]" in prompt


def test_get_profile_defaults(client, auth_headers) -> None:
    headers = auth_headers()
    body = client.get("/api/profile", headers=headers).json()
    assert body["experience_level"] == "junior"
    assert body["learning_pace"] == "normal"
    assert body["interests"] == []
    assert body["prefers_name"] is None
    assert body["custom_notes"] is None


def test_put_profile_partial(client, auth_headers) -> None:
    headers = auth_headers()
    body = client.put("/api/profile", headers=headers, json={"learning_pace": "fast"}).json()
    assert body["learning_pace"] == "fast"
    assert body["experience_level"] == "junior"


def test_put_profile_upsert_with_interests(client, auth_headers) -> None:
    headers = auth_headers()
    response = client.put(
        "/api/profile",
        headers=headers,
        json={
            "prefers_name": "Ala",
            "experience_level": "senior",
            "interests": ["python", "kubernetes"],
            "custom_notes": "hello",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["prefers_name"] == "Ala"
    assert body["experience_level"] == "senior"
    assert body["interests"] == ["python", "kubernetes"]
    assert body["custom_notes"] == "hello"

    again = client.get("/api/profile", headers=headers).json()
    assert again["interests"] == ["python", "kubernetes"]


def test_profile_requires_auth(client) -> None:
    assert client.get("/api/profile").status_code == 401
