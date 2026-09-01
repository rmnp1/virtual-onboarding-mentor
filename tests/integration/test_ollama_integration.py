import httpx
import pytest

from app.chat.llm import generate
from app.config import settings
from app.knowledge_base.ingest import get_embedding, ingest_documents
from app.knowledge_base.retriever import search


def _ollama_ready() -> bool:
    try:
        response = httpx.get(f"{settings.ollama_url}/api/tags", timeout=3.0)
        if response.status_code != 200:
            return False
        models = {str(model.get("name", "")) for model in response.json().get("models", [])}
        return settings.ollama_model in models
    except (httpx.HTTPError, ValueError, KeyError):
        return False


pytestmark = pytest.mark.skipif(
    not _ollama_ready(),
    reason="Ollama or model is not available",
)


@pytest.mark.integration
def test_generate_returns_text() -> None:
    reply = generate(prompt="Repeat the word echo.", system="Be terse.")
    assert isinstance(reply, str)
    assert reply.strip()


@pytest.mark.integration
def test_embeddings_shape() -> None:
    vector = get_embedding("hello world")
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(value, float) for value in vector)


@pytest.mark.integration
def test_search_round_trip(tmp_path) -> None:
    docs_dir = tmp_path / "docs"
    (docs_dir / "en").mkdir(parents=True)
    (docs_dir / "en" / "hr.md").write_text(
        "HR department is located on the third floor and is reachable via the #general channel.",
        encoding="utf-8",
    )
    stats = ingest_documents(str(docs_dir))
    assert stats["files"] == 1
    assert stats["chunks"] >= 1

    results = search("where is HR", language="en", top_k=2)
    assert results
    assert all(result["language"] == "en" for result in results)
    assert "HR" in results[0]["text"]
