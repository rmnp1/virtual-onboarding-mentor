from app.chat.context import build_context
from app.chat.prompts import get_system_prompt


def test_system_prompt_fallback() -> None:
    assert "virtual onboarding mentor" in get_system_prompt("de")


def test_build_context_forwards_search_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_search(
        query: str,
        language: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, object]]:
        captured["query"] = query
        captured["language"] = language
        captured["top_k"] = top_k
        return []

    monkeypatch.setattr("app.chat.context.search", fake_search)
    text, chunks = build_context("Where is HR?", "en", [])
    assert "Where is HR?" in text
    assert "[Relevant knowledge base context]" not in text
    assert chunks == []
    assert captured == {"query": "Where is HR?", "language": "en", "top_k": 3}


def test_build_context_with_chunks(monkeypatch) -> None:
    chunk = {"text": "HR sits in #general", "source": "hr.md", "language": "en", "score": 0.1}
    monkeypatch.setattr("app.chat.context.search", lambda *args, **kwargs: [chunk])
    text, chunks = build_context("hr", "en", [])
    assert "Source: hr.md" in text
    assert "HR sits in #general" in text
    assert chunks == [chunk]


def test_build_context_with_history(monkeypatch) -> None:
    monkeypatch.setattr("app.chat.context.search", lambda *args, **kwargs: [])
    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    text, _ = build_context("question", "pl", history)
    assert "User: hello" in text
    assert "Mentor: hi there" in text


def test_chat_rest_reply_and_sources(client, auth_headers, patch_search, patch_generate) -> None:
    patch_search()
    patch_generate("Hello there")
    response = client.post("/api/chat", headers=auth_headers(), json={"message": "hello"})
    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hello there"
    assert body["sources"] == ["policies.md"]


def test_chat_rest_no_sources(client, auth_headers, patch_search, patch_generate) -> None:
    patch_search([])
    patch_generate("I do not know")
    body = client.post("/api/chat", headers=auth_headers(), json={"message": "hello"}).json()
    assert body["reply"] == "I do not know"
    assert body["sources"] == []


def test_chat_rest_requires_auth(client) -> None:
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401


def test_ws_streams_tokens(client, auth_token, patch_search, patch_generate_stream) -> None:
    token = auth_token()
    patch_search()
    patch_generate_stream(tokens=["Hel", "lo ", "world"])

    with client.websocket_connect(f"/api/chat/ws?token={token}") as websocket:
        websocket.send_json({"message": "hello"})
        frames = []
        while True:
            frame = websocket.receive_json()
            frames.append(frame)
            if frame["type"] == "done":
                break

    assert [frame["type"] for frame in frames] == ["token", "token", "token", "done"]
    assert "".join(frame["content"] for frame in frames) == "Hello world"


def test_ws_sends_error_frame_on_llm_failure(
    client,
    auth_token,
    patch_search,
    patch_generate_stream,
) -> None:
    token = auth_token()
    patch_search()
    patch_generate_stream(exc=RuntimeError("boom"))

    with client.websocket_connect(f"/api/chat/ws?token={token}") as websocket:
        websocket.send_json({"message": "hello"})
        frame = websocket.receive_json()

    assert frame["type"] == "error"
    assert frame["content"] == "LLM service unavailable"


def test_ws_rejects_invalid_token(client) -> None:
    with client.websocket_connect("/api/chat/ws?token=not-a-real-token") as websocket:
        frame = websocket.receive_json()
    assert frame["type"] == "error"
    assert frame["content"] == "Invalid token"
