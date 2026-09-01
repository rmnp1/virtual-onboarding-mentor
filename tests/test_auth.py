from app.auth.password import hash_password, verify_password


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


def test_me_requires_token(client) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_me_invalid_token(client) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer bad.token"})
    assert response.status_code == 401
