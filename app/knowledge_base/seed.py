from app.knowledge_base.ingest import ingest_documents


def main() -> None:
    print("Starting knowledge base ingestion...")
    stats = ingest_documents()
    print(f"Done. Files processed: {stats['files']}, Chunks created: {stats['chunks']}")


if __name__ == "__main__":
    main()
