import json

import httpx

from app.chat.context import build_context
from app.chat.prompts import get_system_prompt


def test_system_prompt_fallback() -> None:
    assert "virtual onboarding mentor" in get_system_prompt("de")
    assert "untrusted data" in get_system_prompt("de")


def test_system_prompt_hardening_polish() -> None:
    assert "niezaufanego źródła" in get_system_prompt("pl")


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


def test_chat_rest_llm_unavailable(client, auth_headers, monkeypatch) -> None:
    def raise_connect_error(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.chat.context.search", raise_connect_error)
    response = client.post("/api/chat", headers=auth_headers(), json={"message": "hello"})
    assert response.status_code == 503
    assert response.json()["detail"] == "LLM service unavailable"


def test_chat_rest_logs_real_exception(client, auth_headers, monkeypatch, caplog) -> None:
    def raise_connect_error(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("app.chat.context.search", raise_connect_error)
    with caplog.at_level("ERROR", logger="app.chat.routes"):
        response = client.post("/api/chat", headers=auth_headers(), json={"message": "hello"})

    assert response.status_code == 503
    records = [r for r in caplog.records if r.name == "app.chat.routes"]
    assert any("ConnectError" in r.getMessage() for r in records)


def test_ws_streams_tokens(client, auth_token, patch_search, patch_generate_stream) -> None:
    token = auth_token()
    patch_search()
    patch_generate_stream(tokens=["Hel", "lo ", "world"])

    with client.websocket_connect("/api/chat/ws") as websocket:
        websocket.send_json({"type": "auth", "content": token})
        websocket.send_json({"message": "hello"})
        frames = []
        while True:
            frame = websocket.receive_json()
            frames.append(frame)
            if frame["type"] == "done":
                break

    assert [frame["type"] for frame in frames] == ["token", "token", "token", "done"]
    assert "".join(frame["content"] for frame in frames) == "Hello world"


def test_ws_handles_ping_pong(
    client,
    auth_token,
    patch_search,
    patch_generate_stream,
) -> None:
    token = auth_token()
    patch_search()
    patch_generate_stream(tokens=["hi"])

    with client.websocket_connect("/api/chat/ws") as websocket:
        websocket.send_json({"type": "auth", "content": token})
        websocket.send_json({"type": "ping", "content": ""})
        ping = websocket.receive_json()
        websocket.send_json({"message": "hello"})
        while True:
            frame = websocket.receive_json()
            if frame["type"] == "done":
                break

    assert ping["type"] == "pong"
    assert frame["type"] == "done"


def test_ws_sends_error_frame_on_llm_failure(
    client,
    auth_token,
    patch_search,
    patch_generate_stream,
) -> None:
    token = auth_token()
    patch_search()
    patch_generate_stream(exc=RuntimeError("boom"))

    with client.websocket_connect("/api/chat/ws") as websocket:
        websocket.send_json({"type": "auth", "content": token})
        websocket.send_json({"message": "hello"})
        frame = websocket.receive_json()

    assert frame["type"] == "error"
    assert frame["content"] == "LLM service unavailable"


def test_ws_logs_stream_exception(
    client,
    auth_token,
    patch_search,
    patch_generate_stream,
    caplog,
) -> None:
    token = auth_token()
    patch_search()
    patch_generate_stream(exc=RuntimeError("boom"))

    with (
        caplog.at_level("ERROR", logger="app.chat.routes"),
        client.websocket_connect("/api/chat/ws") as websocket,
    ):
        websocket.send_json({"type": "auth", "content": token})
        websocket.send_json({"message": "hello"})
        websocket.receive_json()

    records = [r for r in caplog.records if r.name == "app.chat.routes"]
    assert any("RuntimeError" in r.getMessage() for r in records)


def test_ws_rejects_invalid_token(client) -> None:
    with client.websocket_connect("/api/chat/ws") as websocket:
        websocket.send_json({"type": "auth", "content": "not-a-real-token"})
        frame = websocket.receive_json()
    assert frame["type"] == "error"


def test_ws_sends_error_frame_on_search_failure(
    client,
    auth_token,
    monkeypatch,
) -> None:
    def raise_connect_error(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.chat.context.search", raise_connect_error)
    token = auth_token()

    with client.websocket_connect("/api/chat/ws") as websocket:
        websocket.send_json({"type": "auth", "content": token})
        websocket.send_json({"message": "hello"})
        frame = websocket.receive_json()

    assert frame["type"] == "error"
    assert frame["content"] == "LLM service unavailable"


def test_chat_rest_rate_limited(client, auth_headers, patch_search, patch_generate) -> None:
    headers = auth_headers()
    patch_search()
    patch_generate("ok")
    for _ in range(20):
        response = client.post("/api/chat", headers=headers, json={"message": "hi"})
        assert response.status_code == 200
    response = client.post("/api/chat", headers=headers, json={"message": "hi"})
    assert response.status_code == 429


def test_ws_chat_rate_limited(client, auth_token, patch_search, patch_generate_stream) -> None:
    from app.auth.ratelimit import chat_ip

    token = auth_token()
    patch_search()
    patch_generate_stream(tokens=["ok"])

    for _ in range(20):
        chat_ip.allowed("testclient")

    with client.websocket_connect("/api/chat/ws") as websocket:
        websocket.send_json({"type": "auth", "content": token})
        websocket.send_json({"message": "hi"})
        frame = websocket.receive_json()

    assert frame["type"] == "error"
    assert frame["content"] == "Too many requests"


def _mock_llm_client(monkeypatch, handler):
    from app.chat import llm

    real_client = httpx.Client

    def _client(**kwargs):
        kwargs.pop("transport", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(llm.httpx, "Client", _client)


def test_gemini_generate_parse_non_stream(monkeypatch) -> None:
    from app.chat import llm
    from app.config import settings

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        body = json.loads(request.content)
        assert body["model"] == "gemini-model"
        assert body["stream"] is False
        assert body["messages"][0] == {"role": "system", "content": "sys"}
        assert body["messages"][1] == {"role": "user", "content": "prompt"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Gemini reply"}}]},
        )

    _mock_llm_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "gemini-model")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    reply = llm.generate("prompt", "sys")
    assert reply == "Gemini reply"


def test_gemini_generate_empty_choices(monkeypatch) -> None:
    from app.chat import llm
    from app.config import settings

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    _mock_llm_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "llm_provider", "gemini")

    assert llm.generate("prompt", "sys") == ""


def test_gemini_stream_parses_delta(monkeypatch) -> None:
    from app.chat import llm
    from app.config import settings

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["stream"] is True
        payloads = [
            "data: " + json.dumps({"choices": [{"delta": {"content": "Hel"}}]}) + "\n",
            "data: " + json.dumps({"choices": [{"delta": {"content": "lo"}}]}) + "\n",
            "data: [DONE]\n",
        ]
        return httpx.Response(
            200,
            content="".join(payloads),
            headers={"content-type": "text/event-stream"},
        )

    _mock_llm_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "llm_provider", "gemini")
    monkeypatch.setattr(settings, "llm_model", "gemini-model")
    monkeypatch.setattr(settings, "llm_api_key", "k")

    tokens = list(llm.generate_stream("prompt", "sys"))
    assert tokens == ["Hel", "lo"]


def test_gemini_stream_skips_empty_delta(monkeypatch) -> None:
    from app.chat import llm
    from app.config import settings

    def handler(request: httpx.Request) -> httpx.Response:
        payloads = [
            "data: " + json.dumps({"choices": [{"delta": {"content": None}}]}) + "\n",
            "data: " + json.dumps({"choices": [{"delta": {"content": ""}}]}) + "\n",
            "data: " + json.dumps({"choices": [{"delta": {"content": "ok"}}]}) + "\n",
            "data: [DONE]\n",
        ]
        return httpx.Response(
            200,
            content="".join(payloads),
            headers={"content-type": "text/event-stream"},
        )

    _mock_llm_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "llm_provider", "gemini")

    assert list(llm.generate_stream("prompt", "sys")) == ["ok"]


def test_gemini_stream_handles_non_data_lines(monkeypatch) -> None:
    from app.chat import llm
    from app.config import settings

    def handler(request: httpx.Request) -> httpx.Response:
        payloads = [
            ": keep-alive comment\n",
            "data: " + json.dumps({"choices": [{"delta": {"content": "x"}}]}) + "\n",
            "unexpected\n",
            "data: [DONE]\n",
        ]
        return httpx.Response(
            200,
            content="".join(payloads),
            headers={"content-type": "text/event-stream"},
        )

    _mock_llm_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "llm_provider", "gemini")

    assert list(llm.generate_stream("prompt", "sys")) == ["x"]


def test_ollama_default_provider_still_used(monkeypatch) -> None:
    from app.chat import llm
    from app.config import settings

    payload = {"model": "llama3", "response": "ollama reply"}
    url = f"{settings.ollama_url}/api/generate"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == url
        return httpx.Response(200, json=payload)

    _mock_llm_client(monkeypatch, handler)
    monkeypatch.setattr(settings, "llm_provider", "ollama")

    assert llm.generate("prompt", "sys") == "ollama reply"
