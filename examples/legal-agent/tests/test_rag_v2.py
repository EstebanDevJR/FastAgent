from app.rag.retriever import Retriever


def test_retriever_hybrid_returns_ranked_docs() -> None:
    retriever = Retriever(vector_db="Qdrant")
    retriever.index("FastAgent supports contract analysis with retrieval and citations.")
    retriever.index("Use Qdrant for vector search and lexical reranking in production.")
    docs = retriever.retrieve("qdrant contract analysis", top_k=2)
    assert len(docs) >= 1
    assert any("qdrant" in doc.lower() or "contract" in doc.lower() for doc in docs)


def test_retriever_deduplicates_chunks() -> None:
    retriever = Retriever(vector_db="Qdrant")
    text = "A" * 600
    retriever.index(text)
    retriever.index(text)
    assert len(retriever._chunks) > 0
    assert len(retriever._chunks) == len({item["id"] for item in retriever._chunks})
