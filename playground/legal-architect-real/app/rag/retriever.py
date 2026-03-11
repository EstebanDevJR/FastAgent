from __future__ import annotations

import hashlib

from app.rag.chunker import chunk_text, dedupe_chunks
from app.rag.hybrid import hybrid_search
from app.rag.reranker import rerank_results


class Retriever:
    def __init__(self, vector_db: str = "None") -> None:
        self.vector_db = vector_db
        self._chunks: list[dict] = []
        self._hashes: set[str] = set()

    def index(self, text: str, source: str = "inline") -> None:
        chunks = dedupe_chunks(chunk_text(text))
        for chunk in chunks:
            digest = hashlib.sha1(chunk.encode("utf-8")).hexdigest()
            if digest in self._hashes:
                continue
            self._hashes.add(digest)
            self._chunks.append(
                {
                    "id": digest,
                    "text": chunk,
                    "source": source,
                }
            )

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        if self.vector_db.lower() == "none":
            return []
        if not self._chunks:
            return ["No indexed documents yet."]

        candidates = hybrid_search(query=query, chunks=self._chunks, top_k=max(top_k * 4, top_k))
        reranked = rerank_results(query=query, candidates=candidates, top_k=top_k)
        docs = [str(item.get("text", "")).strip() for item in reranked if str(item.get("text", "")).strip()]
        return docs or ["No indexed documents yet."]
