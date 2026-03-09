def rag_hint(vector_db: str) -> str:
    if (vector_db or "").lower() == "none":
        return "RAG disabled"
    return f"RAG enabled with {vector_db}"
