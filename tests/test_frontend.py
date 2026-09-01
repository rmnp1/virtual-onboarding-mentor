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
