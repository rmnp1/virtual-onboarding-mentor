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
    monkeypatch.setattr("app.knowledge_base.retriever.get_collection", lambda: fake)
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
    monkeypatch.setattr("app.knowledge_base.retriever.get_collection", lambda: fake)
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

    monkeypatch.setattr("app.knowledge_base.ingest.get_collection", lambda: FakeCollection())
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
