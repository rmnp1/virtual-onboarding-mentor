from app.auth.password import hash_password, verify_password
from app.config import settings


def test_secret_key_is_strong() -> None:
    assert len(settings.secret_key) >= 32


def test_password_roundtrip() -> None:
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_password_hash_is_salted() -> None:
    assert hash_password("secret123") != hash_password("secret123")


def test_register_defaults(client, user_factory) -> None:
    user = user_factory()
    body = client.get("/api/auth/me", headers=user["headers"]).json()
    assert body["id"] == user["id"]
    assert body["role"] == "employee"
    assert body["language"] == "en"


def test_register_duplicate_email(client) -> None:
    payload = {"email": "dup@example.com", "password": "password1"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"


def test_register_invalid_email(client) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "not-an-email", "password": "password1"},
    )
    assert response.status_code == 422


def test_register_rejects_role_field(client) -> None:
    response = client.post(
        "/api/auth/register",
        json={
            "email": "esc@example.com",
            "password": "password1",
            "full_name": "Esc",
            "role": "admin",
        },
    )
    assert response.status_code == 422
    registered = client.post(
        "/api/auth/login",
        json={"email": "esc@example.com", "password": "password1"},
    )
    assert registered.status_code == 401


def test_register_custom_role_and_language(client, user_factory) -> None:
    user = user_factory(role="hr", language="pl", full_name="Anna")
    response = client.get("/api/auth/me", headers=user["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "hr"
    assert body["language"] == "pl"
    assert body["full_name"] == "Anna"


def test_login_success(client, user_factory) -> None:
    user = user_factory()
    response = client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": user["password"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 20


def test_login_wrong_password(client, user_factory) -> None:
    user = user_factory()
    response = client.post(
        "/api/auth/login",
        json={"email": user["email"], "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_email(client) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "password1"},
    )
    assert response.status_code == 401


def test_register_rate_limited(client) -> None:
    for i in range(10):
        payload = {"email": f"rl-{i}@example.com", "password": "password1"}
        assert client.post("/api/auth/register", json=payload).status_code == 201
    response = client.post(
        "/api/auth/register",
        json={"email": "rl-over@example.com", "password": "password1"},
    )
    assert response.status_code == 429


def test_login_email_rate_limited(client) -> None:
    client.post(
        "/api/auth/register",
        json={"email": "rl-e@example.com", "password": "password1"},
    )
    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={"email": "rl-e@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
    response = client.post(
        "/api/auth/login",
        json={"email": "rl-e@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 429


def test_register_rejects_short_password(client) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "password": "short"},
    )
    assert response.status_code == 422


def test_register_rejects_long_password_bytes(client) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "wide@example.com", "password": "😀" * 19},
    )
    assert response.status_code == 422


def test_login_rejects_oversized_password(client) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "big@example.com", "password": "x" * 73},
    )
    assert response.status_code == 422


def test_me_requires_token(client) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_me_invalid_token(client) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token"})
    assert response.status_code == 401


def test_auth_config_default(client) -> None:
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    assert response.json() == {"invite_required": False}


def test_auth_config_invite_required(client, monkeypatch) -> None:
    monkeypatch.setattr("app.auth.routes.settings.invite_required", True)
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    assert response.json() == {"invite_required": True}


def test_register_requires_invite_code(client, monkeypatch) -> None:
    monkeypatch.setattr("app.auth.routes.settings.invite_required", True)
    monkeypatch.setattr("app.auth.routes.settings.invite_codes", "SECRET123")
    response = client.post(
        "/api/auth/register",
        json={"email": "inv@example.com", "password": "password1"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Valid invite code required"


def test_register_rejects_invalid_invite_code(client, monkeypatch) -> None:
    monkeypatch.setattr("app.auth.routes.settings.invite_required", True)
    monkeypatch.setattr("app.auth.routes.settings.invite_codes", "SECRET123")
    response = client.post(
        "/api/auth/register",
        json={"email": "inv@example.com", "password": "password1", "invite_code": "WRONG"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Valid invite code required"


def test_register_accepts_valid_invite_code(client, monkeypatch) -> None:
    monkeypatch.setattr("app.auth.routes.settings.invite_required", True)
    monkeypatch.setattr("app.auth.routes.settings.invite_codes", "alpha,BETA")
    response = client.post(
        "/api/auth/register",
        json={"email": "inv@example.com", "password": "password1", "invite_code": "beta"},
    )
    assert response.status_code == 201
