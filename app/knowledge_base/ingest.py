import logging
import time
from pathlib import Path

import httpx

from app.config import settings
from app.knowledge_base import store

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _response_snippet(response: httpx.Response | None, limit: int = 500) -> str:
    if response is None:
        return ""
    body = ""
    try:
        body = response.text[:limit]
    except Exception:
        try:
            body = response.content[:limit].decode("utf-8", errors="replace")
        except Exception:
            body = "<unreadable>"
    return body


def _is_retryable(status_code: int | None) -> bool:
    return status_code is not None and status_code in _RETRYABLE_STATUS


def _retry_delay(attempt: int) -> float:
    configured: float = settings.gemini_retry_base_delay
    base = max(configured, 0.1)
    return float(base * (2 ** (attempt - 1)))


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
    url = f"{GEMINI_OPENAI_BASE}/embeddings"
    for attempt in range(1, settings.gemini_max_retries + 1):
        try:
            response = httpx.post(
                url,
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
        except httpx.HTTPError as exc:
            resp = getattr(exc, "response", None)
            status = resp.status_code if resp is not None else None
            if _is_retryable(status) and attempt < settings.gemini_max_retries:
                logger.warning(
                    "gemini embeddings got %s on attempt %d/%d, retrying in %.1fs",
                    status,
                    attempt,
                    settings.gemini_max_retries,
                    _retry_delay(attempt),
                )
                time.sleep(_retry_delay(attempt))
                continue
            body = _response_snippet(resp)
            logger.error(
                "gemini embeddings failed: %s status=%s url=%s body=%r: %s",
                type(exc).__name__,
                status,
                url,
                body,
                exc,
                exc_info=exc,
            )
            raise
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
