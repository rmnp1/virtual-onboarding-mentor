from pathlib import Path

import chromadb
import httpx

from app.config import settings

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

COLLECTION_NAME = "onboarding_knowledge"


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return client.get_or_create_collection(name=COLLECTION_NAME)


def get_embedding(text: str) -> list[float]:
    response = httpx.post(
        f"{settings.ollama_url}/api/embeddings",
        json={"model": settings.ollama_embedding_model, "prompt": text},
    )
    response.raise_for_status()
    data: dict[str, list[float]] = response.json()
    return data["embedding"]


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
    collection = get_collection()

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
            metadatas: list[dict[str, str | int | float | bool | None]] = []

            for i, chunk in enumerate(chunks):
                ids.append(f"{language}_{md_file.stem}_{i}")
                embeddings.append(get_embedding(chunk))
                documents.append(chunk)
                metadatas.append({"source": md_file.name, "language": language})

            collection.upsert(
                ids=ids,
                embeddings=embeddings,  # type: ignore[arg-type]
                documents=documents,
                metadatas=metadatas,  # type: ignore[arg-type]
            )

            stats["files"] += 1
            stats["chunks"] += len(chunks)

    return stats
