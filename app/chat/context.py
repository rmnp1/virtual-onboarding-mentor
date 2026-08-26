from app.knowledge_base.retriever import search


def build_context(query: str, language: str, history: list[dict[str, str]], top_k: int = 3) -> str:
    chunks = search(query, language=language, top_k=top_k)

    context_parts: list[str] = []

    if chunks:
        context_parts.append("[Relevant knowledge base context]")
        for chunk in chunks:
            source = chunk.get("source", "")
            text = chunk.get("text", "")
            context_parts.append(f"Source: {source}\n{text}")

    if history:
        context_parts.append("[Conversation history]")
        for msg in history[-10:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            label = "User" if role == "user" else "Mentor"
            context_parts.append(f"{label}: {content}")

    context_parts.append(f"[User question]\n{query}")

    return "\n\n".join(context_parts)
