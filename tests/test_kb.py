from app.knowledge_base.ingest import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    chunk_text,
    get_embedding,
    ingest_documents,
)
from app.knowledge_base.retriever import search


def test_chunk_text_boundaries() -> None:
    text = "a" * 1000
    chunks = chunk_text(text)
    assert len(chunks) == 3
    assert [len(c) for c in chunks] == [CHUNK_SIZE, CHUNK_SIZE, 200]
    expected_starts = [0, CHUNK_SIZE - CHUNK_OVERLAP, 2 * (CHUNK_SIZE - CHUNK_OVERLAP)]
    for chunk, start in zip(chunks, expected_starts, strict=True):
        assert text.startswith(chunk, start)


def test_search_maps_results(monkeypatch) -> None:
    class FakeCollection:
        def query(self, **kwargs: object) -> dict[str, object]:
            self.called_with = kwargs
            return {
                "documents": [["chunk one", "chunk two"]],
                "metadatas": [
                    [
                        {"source": "a.md", "language": "en"},
                        {"source": "b.md", "language": "en"},
                    ]
                ],
                "distances": [[0.1, 0.2]],
            }

    fake = FakeCollection()
    monkeypatch.setattr("app.knowledge_base.store.get_collection", lambda: fake)
    monkeypatch.setattr("app.knowledge_base.retriever.get_embedding", lambda text: [0.0] * 8)

    results = search("query", language="en", top_k=2)
    assert len(results) == 2
    assert results[0]["text"] == "chunk one"
    assert results[0]["source"] == "a.md"
    assert results[0]["language"] == "en"
    assert results[0]["score"] == 0.1
    assert fake.called_with["where"] == {"language": "en"}
    assert fake.called_with["n_results"] == 2


def test_search_without_language_no_filter(monkeypatch) -> None:
    class FakeCollection:
        def query(self, **kwargs: object) -> dict[str, object]:
            self.called_with = kwargs
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    fake = FakeCollection()
    monkeypatch.setattr("app.knowledge_base.store.get_collection", lambda: fake)
    monkeypatch.setattr("app.knowledge_base.retriever.get_embedding", lambda text: [0.0])
    search("query", top_k=3)
    assert fake.called_with["where"] is None


def test_get_embedding_uses_long_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": [0.5, 0.25] * 4}

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.knowledge_base.ingest.httpx.post", fake_post)
    embedding = get_embedding("hello")
    assert embedding == [0.5, 0.25] * 4
    assert captured["timeout"] == 120.0


def test_get_embedding_caches_repeat_query(monkeypatch) -> None:
    from app.knowledge_base.ingest import _EMBEDDING_CACHE

    calls: list[str] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"embedding": [0.25, 0.5]}

    def fake_post(*args: object, **kwargs: object) -> FakeResponse:
        calls.append(str(kwargs.get("json")))
        return FakeResponse()

    _EMBEDDING_CACHE.clear()
    monkeypatch.setattr("app.knowledge_base.ingest.httpx.post", fake_post)
    first = get_embedding("repeat me")
    second = get_embedding("repeat me")
    assert first == second == [0.25, 0.5]
    assert len(calls) == 1


def test_ingest_documents_stats_and_upsert(tmp_path, monkeypatch) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "en").mkdir(parents=True)
    (docs_dir / "en" / "hr.md").write_text(
        "HR department is on the third floor. " * 40,
        encoding="utf-8",
    )

    upserts: list[dict[str, object]] = []

    class FakeCollection:
        def upsert(self, **kwargs: object) -> None:
            upserts.append(kwargs)

    monkeypatch.setattr("app.knowledge_base.store.get_collection", lambda: FakeCollection())
    monkeypatch.setattr(
        "app.knowledge_base.ingest.get_embedding",
        lambda text: [0.5, 0.25] * 4,
    )

    stats = ingest_documents(str(docs_dir))
    assert stats["files"] == 1
    assert stats["chunks"] >= 1
    assert len(upserts) == 1
    call = upserts[0]
    assert call["ids"][0] == "en_hr_0"
    assert len(call["documents"]) == stats["chunks"]
    assert all(meta["language"] == "en" for meta in call["metadatas"])


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def test_gemini_embedding_parses_response(monkeypatch) -> None:
    from app.config import settings
    from app.knowledge_base.ingest import get_embedding

    captured: dict[str, object] = {}

    def fake_post(*args: object, **kwargs: object) -> _FakeResponse:
        captured["url"] = args[0]
        captured.update(kwargs)
        return _FakeResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

    monkeypatch.setattr("app.knowledge_base.ingest.httpx.post", fake_post)
    monkeypatch.setattr(settings, "embedding_provider", "gemini")
    monkeypatch.setattr(settings, "embedding_model", "gemini-embedding-001")
    monkeypatch.setattr(settings, "embedding_api_key", "test-key")

    embedding = get_embedding("hello")
    assert embedding == [0.1, 0.2, 0.3]


def test_gemini_embedding_sends_expected_payload(monkeypatch) -> None:
    from app.config import settings
    from app.knowledge_base.ingest import get_embedding

    captured: dict[str, object] = {}

    def fake_post(*args: object, **kwargs: object) -> _FakeResponse:
        captured["url"] = args[0]
        captured["headers"] = kwargs.get("headers")
        captured["json"] = kwargs.get("json")
        captured["timeout"] = kwargs.get("timeout")
        return _FakeResponse({"data": [{"embedding": [1.0]}]})

    monkeypatch.setattr("app.knowledge_base.ingest.httpx.post", fake_post)
    monkeypatch.setattr(settings, "embedding_provider", "gemini")
    monkeypatch.setattr(settings, "embedding_model", "gemini-embedding-001")
    monkeypatch.setattr(settings, "embedding_api_key", "test-key")

    get_embedding("hello")
    assert captured["url"] == ("https://generativelanguage.googleapis.com/v1beta/openai/embeddings")
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"] == {"model": "gemini-embedding-001", "input": "hello"}
    assert captured["timeout"] == 120.0


def test_gemini_embedding_empty_data_returns_empty(monkeypatch) -> None:
    from app.config import settings
    from app.knowledge_base.ingest import get_embedding

    def fake_post(*args: object, **kwargs: object) -> _FakeResponse:
        return _FakeResponse({"data": []})

    monkeypatch.setattr("app.knowledge_base.ingest.httpx.post", fake_post)
    monkeypatch.setattr(settings, "embedding_provider", "gemini")

    assert get_embedding("hello") == []


def test_ollama_default_embedding_still_used(monkeypatch) -> None:
    from app.config import settings
    from app.knowledge_base.ingest import get_embedding

    captured: dict[str, object] = {}

    def fake_post(*args: object, **kwargs: object) -> _FakeResponse:
        captured["url"] = args[0]
        captured["json"] = kwargs.get("json")
        return _FakeResponse({"embedding": [0.5, 0.25]})

    monkeypatch.setattr("app.knowledge_base.ingest.httpx.post", fake_post)
    monkeypatch.setattr(settings, "embedding_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_embedding_model", "nomic-embed-text")

    embedding = get_embedding("hello")
    assert embedding == [0.5, 0.25]
    assert captured["url"] == f"{settings.ollama_url}/api/embeddings"
    assert captured["json"] == {
        "model": "nomic-embed-text",
        "prompt": "hello",
    }


def test_store_detects_postgres_url(monkeypatch) -> None:
    from app.config import settings
    from app.knowledge_base import store

    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@h/db")
    assert store._is_postgres() is True


def test_store_detects_sqlite_url(monkeypatch) -> None:
    from app.config import settings
    from app.knowledge_base import store

    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/db.sqlite")
    assert store._is_postgres() is False


def test_upsert_chroma_delegation(monkeypatch) -> None:
    from app.config import settings
    from app.knowledge_base import store

    captured: dict[str, object] = {}

    class FakeCollection:
        def upsert(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(settings, "database_url", "sqlite:///./data/db.sqlite")
    monkeypatch.setattr("app.knowledge_base.store.get_collection", lambda: FakeCollection())

    store.upsert(
        ids=["en_hr_0"],
        embeddings=[[0.1, 0.2]],
        documents=["text"],
        metadatas=[{"source": "hr.md", "language": "en"}],
    )

    assert captured["ids"] == ["en_hr_0"]
    assert captured["documents"] == ["text"]


def test_knowledge_chunk_schema() -> None:
    from app.knowledge_base.store import KnowledgeChunk

    assert KnowledgeChunk.__tablename__ == "knowledge_chunks"
    columns = {c.name: c for c in KnowledgeChunk.__table__.columns}
    assert {"chunk_id", "language", "source", "content", "embedding"} <= set(columns)
    constraint = KnowledgeChunk.__table__.constraints
    assert any(getattr(c, "name", "") == "uq_knowledge_chunk_id" for c in constraint)
