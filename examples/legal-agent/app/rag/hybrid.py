from __future__ import annotations

import math


def hybrid_search(query: str, chunks: list[dict], top_k: int = 10) -> list[dict]:
    if not chunks:
        return []
    q = query.strip().lower()
    if not q:
        return chunks[:top_k]

    scored: list[tuple[float, dict]] = []
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        lexical = _lexical_score(q, text.lower())
        semantic = _semantic_proxy_score(q, text.lower())
        score = (0.45 * lexical) + (0.55 * semantic)
        enriched = dict(chunk)
        enriched["hybrid_score"] = round(score, 6)
        scored.append((score, enriched))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[: max(1, top_k)]]


def _lexical_score(query: str, text: str) -> float:
    q_tokens = [token for token in query.split() if token]
    if not q_tokens:
        return 0.0
    hits = sum(1 for token in q_tokens if token in text)
    return hits / len(q_tokens)


def _semantic_proxy_score(query: str, text: str) -> float:
    # Lightweight proxy so scaffold stays dependency-free.
    query_vec = _trigram_vector(query)
    text_vec = _trigram_vector(text)
    return _cosine(query_vec, text_vec)


def _trigram_vector(text: str) -> dict[str, float]:
    cleaned = f"  {text}  "
    vec: dict[str, float] = {}
    for idx in range(max(0, len(cleaned) - 2)):
        tri = cleaned[idx : idx + 3]
        vec[tri] = vec.get(tri, 0.0) + 1.0
    return vec


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    for key, value in a.items():
        dot += value * b.get(key, 0.0)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
