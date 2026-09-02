from pathlib import Path

import httpx

from app.config import settings
from app.knowledge_base import store

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


def _get_ollama_embedding(text: str) -> list[float]:
    response = httpx.post(
        f"{settings.ollama_url}/api/embeddings",
        json={"model": settings.ollama_embedding_model, "prompt": text},
        timeout=120.0,
    )
    response.raise_for_status()
    data: dict[str, list[float]] = response.json()
    return data["embedding"]


def _get_gemini_embedding(text: str) -> list[float]:
    headers = {
        "Authorization": f"Bearer {settings.embedding_api_key}",
        "Content-Type": "application/json",
    }
    response = httpx.post(
        f"{GEMINI_OPENAI_BASE}/embeddings",
        headers=headers,
        json={"model": settings.embedding_model, "input": text},
        timeout=120.0,
    )
    response.raise_for_status()
    data: dict[str, object] = response.json()
    items = data.get("data")
    if isinstance(items, list) and items and isinstance(items[0], dict):
        embedding = items[0].get("embedding")
        if isinstance(embedding, list):
            return [float(x) for x in embedding]
    return []


def get_embedding(text: str) -> list[float]:
    if settings.embedding_provider == "gemini":
        return _get_gemini_embedding(text)
    return _get_ollama_embedding(text)


def chunk_text(text: str) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def ingest_documents(docs_dir: str = "data/documents") -> dict[str, int]:
    docs_path = Path(docs_dir)

    stats: dict[str, int] = {"files": 0, "chunks": 0}

    for lang_dir in sorted(docs_path.iterdir()):
        if not lang_dir.is_dir():
            continue
        language = lang_dir.name

        for md_file in sorted(lang_dir.glob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            chunks = chunk_text(text)

            ids: list[str] = []
            embeddings: list[list[float]] = []
            documents: list[str] = []
            metadatas: list[dict[str, object]] = []

            for i, chunk in enumerate(chunks):
                ids.append(f"{language}_{md_file.stem}_{i}")
                embeddings.append(get_embedding(chunk))
                documents.append(chunk)
                metadatas.append({"source": md_file.name, "language": language})

            store.upsert(ids, embeddings, documents, metadatas)

            stats["files"] += 1
            stats["chunks"] += len(chunks)

    return stats
