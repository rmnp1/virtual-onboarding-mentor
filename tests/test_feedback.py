def test_post_general_feedback(client, auth_headers) -> None:
    headers = auth_headers()
    response = client.post(
        "/api/feedback",
        headers=headers,
        json={"rating": 5, "comment": "Great mentor"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["rating"] == 5
    assert body["comment"] == "Great mentor"
    assert body["scenario_id"] is None
    assert body["id"] > 0
    assert "created_at" in body


def test_post_scenario_feedback(client, auth_headers) -> None:
    headers = auth_headers()
    response = client.post(
        "/api/feedback",
        headers=headers,
        json={"rating": 4, "scenario_id": "welcome"},
    )
    assert response.status_code == 201
    assert response.json()["scenario_id"] == "welcome"


def test_post_rating_bounds(client, auth_headers) -> None:
    headers = auth_headers()
    assert client.post("/api/feedback", headers=headers, json={"rating": 0}).status_code == 422
    assert client.post("/api/feedback", headers=headers, json={"rating": 6}).status_code == 422
    assert client.post("/api/feedback", headers=headers, json={}).status_code == 422


def test_post_unknown_scenario(client, auth_headers) -> None:
    headers = auth_headers()
    response = client.post(
        "/api/feedback",
        headers=headers,
        json={"rating": 3, "scenario_id": "nope"},
    )
    assert response.status_code == 404


def test_post_feedback_requires_auth(client) -> None:
    assert client.post("/api/feedback", json={"rating": 5}).status_code == 401


def test_get_own_feedback_only(client, auth_headers) -> None:
    headers_a = auth_headers()
    headers_b = auth_headers()
    client.post("/api/feedback", headers=headers_a, json={"rating": 5})
    client.post("/api/feedback", headers=headers_b, json={"rating": 1})
    assert len(client.get("/api/feedback", headers=headers_a).json()) == 1
    assert len(client.get("/api/feedback", headers=headers_b).json()) == 1


def test_get_feedback_ordered_desc(client, auth_headers) -> None:
    headers = auth_headers()
    first = client.post("/api/feedback", headers=headers, json={"rating": 3}).json()
    second = client.post("/api/feedback", headers=headers, json={"rating": 4}).json()
    ids = [entry["id"] for entry in client.get("/api/feedback", headers=headers).json()]
    assert ids == [second["id"], first["id"]]
