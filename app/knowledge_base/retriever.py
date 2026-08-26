from app.knowledge_base.ingest import get_collection, get_embedding


def search(query: str, language: str | None = None, top_k: int = 5) -> list[dict[str, object]]:
    collection = get_collection()
    query_embedding = get_embedding(query)

    where_filter: dict[str, str] | None = None
    if language:
        where_filter = {"language": language}

    results = collection.query(
        query_embeddings=[query_embedding],  # type: ignore[arg-type]
        n_results=top_k,
        where=where_filter,  # type: ignore[arg-type]
        include=["documents", "metadatas", "distances"],
    )

    output: list[dict[str, object]] = []
    documents = results.get("documents")
    metadatas = results.get("metadatas")
    distances = results.get("distances")

    if documents and metadatas and distances:
        for doc, meta, dist in zip(documents[0], metadatas[0], distances[0], strict=True):
            output.append(
                {
                    "text": doc,
                    "source": meta.get("source", ""),
                    "language": meta.get("language", ""),
                    "score": dist,
                }
            )

    return output
