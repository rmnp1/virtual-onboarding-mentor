from typing import cast

from app.knowledge_base import store


def main() -> None:
    if not store._is_postgres():
        raise SystemExit("Migration requires a PostgreSQL backend (postgresql+psycopg://)")

    chroma_collection = store.get_collection()
    data = chroma_collection.get(include=["embeddings", "documents", "metadatas"])

    ids = [str(i) for i in data.get("ids", [])]
    embeddings = [list(e) for e in (data.get("embeddings") or [])]
    documents = [str(d) for d in (data.get("documents") or [])]
    metadatas: list[dict[str, object]] = [
        cast(dict[str, object], m) for m in (data.get("metadatas") or [])
    ]
    if not ids:
        print("No ChromaDB data to migrate.")
        return

    store.upsert(ids, embeddings, documents, metadatas)
    print(f"Migrated {len(ids)} chunks from ChromaDB to PostgreSQL + pgvector.")
    print("ChromaDB data was NOT deleted.")


if __name__ == "__main__":
    main()
