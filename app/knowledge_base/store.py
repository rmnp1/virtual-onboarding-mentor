import chromadb
from pgvector.sqlalchemy import Vector
from sqlalchemy import Integer, String, Text, UniqueConstraint, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings
from app.models.base import SessionLocal, engine

COLLECTION_NAME = "onboarding_knowledge"

VECTOR_DIM = settings.embedding_dimension


def _is_postgres() -> bool:
    return settings.database_url.startswith("postgresql")


class _VectorBase(DeclarativeBase):
    pass


class KnowledgeChunk(_VectorBase):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("chunk_id", name="uq_knowledge_chunk_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIM), nullable=True)


_vector_initialized = False


def init_vector_store() -> None:
    global _vector_initialized
    if not _is_postgres() or _vector_initialized:
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    _VectorBase.metadata.create_all(bind=engine)
    _vector_initialized = True


def get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return client.get_or_create_collection(name=COLLECTION_NAME)


def _meta(metadatas: list[dict[str, object]], index: int, key: str) -> str:
    if index < len(metadatas):
        value = metadatas[index].get(key)
        if value is not None:
            return str(value)
    return ""


def _upsert_postgres(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, object]],
) -> None:
    init_vector_store()
    rows = []
    for i, cid in enumerate(ids):
        rows.append(
            {
                "chunk_id": cid,
                "language": _meta(metadatas, i, "language"),
                "source": _meta(metadatas, i, "source"),
                "content": documents[i] if i < len(documents) else "",
                "embedding": embeddings[i] if i < len(embeddings) else None,
            }
        )
    if not rows:
        return
    stmt = pg_insert(KnowledgeChunk).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["chunk_id"],
        set_={
            "language": stmt.excluded.language,
            "source": stmt.excluded.source,
            "content": stmt.excluded.content,
            "embedding": stmt.excluded.embedding,
        },
    )
    session = SessionLocal()
    try:
        session.execute(stmt)
        session.commit()
    finally:
        session.close()


def _upsert_chroma(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, object]],
) -> None:
    collection = get_collection()
    collection.upsert(
        ids=ids,
        embeddings=embeddings,  # type: ignore[arg-type]
        documents=documents,
        metadatas=metadatas,  # type: ignore[arg-type]
    )


def upsert(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, object]],
) -> None:
    if _is_postgres():
        _upsert_postgres(ids, embeddings, documents, metadatas)
    else:
        _upsert_chroma(ids, embeddings, documents, metadatas)


def _query_postgres(
    query_embedding: list[float],
    language: str | None,
    top_k: int,
) -> list[dict[str, object]]:
    init_vector_store()
    distance = KnowledgeChunk.embedding.l2_distance(query_embedding).label("score")
    stmt = (
        select(
            KnowledgeChunk.content,
            KnowledgeChunk.source,
            KnowledgeChunk.language,
            distance,
        )
        .order_by(distance)
        .limit(top_k)
    )
    if language:
        stmt = stmt.where(KnowledgeChunk.language == language)

    session = SessionLocal()
    try:
        rows = session.execute(stmt).all()
    finally:
        session.close()
    return [
        {
            "text": row[0],
            "source": row[1],
            "language": row[2],
            "score": float(row[3]),
        }
        for row in rows
    ]


def _query_chroma(
    query_embedding: list[float],
    language: str | None,
    top_k: int,
) -> list[dict[str, object]]:
    collection = get_collection()
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
        meta_rows = metadatas[0] if metadatas else []
        dist_rows = distances[0] if distances else []
        for doc, meta, dist in zip(documents[0], meta_rows, dist_rows, strict=True):
            output.append(
                {
                    "text": doc,
                    "source": str(meta.get("source", "")),
                    "language": str(meta.get("language", "")),
                    "score": dist,
                }
            )
    return output


def query(
    query_embedding: list[float],
    language: str | None = None,
    top_k: int = 5,
) -> list[dict[str, object]]:
    if _is_postgres():
        return _query_postgres(query_embedding, language, top_k)
    return _query_chroma(query_embedding, language, top_k)
