STATIC_PATHS = [
    "/style.css",
    "/app.js",
    "/lib.js",
    "/views/auth.js",
    "/views/chat.js",
    "/views/scenarios.js",
    "/views/profile.js",
    "/views/feedback.js",
    "/views/metrics.js",
]


def test_index_served(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Onboarding Mentor" in response.text


def test_static_assets_served(client) -> None:
    for path in STATIC_PATHS:
        assert client.get(path).status_code == 200, path


def test_unknown_path_is_404(client) -> None:
    assert client.get("/no-such-page").status_code == 404


def test_api_not_shadowed(client, auth_headers) -> None:
    assert client.get("/api/scenarios").status_code == 401
    assert client.get("/api/scenarios", headers=auth_headers()).status_code == 200


def test_cors_not_enabled_by_default(client) -> None:
    response = client.get("/api/auth/me", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


def test_security_headers(client) -> None:
    response = client.get("/")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("referrer-policy") == "no-referrer"


def test_docs_enabled_by_default(client) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_disabled(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import build_app

    secret = "test-only-secret-key-which-is-longer-than-32-bytes"
    test_app = build_app(Settings(expose_docs=False, secret_key=secret))
    with TestClient(test_app) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
