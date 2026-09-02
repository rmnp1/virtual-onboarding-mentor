from app.knowledge_base import store
from app.knowledge_base.ingest import get_embedding


def search(query: str, language: str | None = None, top_k: int = 5) -> list[dict[str, object]]:
    query_embedding = get_embedding(query)
    return store.query(query_embedding, language=language, top_k=top_k)
