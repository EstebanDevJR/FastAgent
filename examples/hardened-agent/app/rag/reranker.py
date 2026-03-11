from __future__ import annotations


def rerank_results(query: str, candidates: list[dict], top_k: int = 3) -> list[dict]:
    if not candidates:
        return []

    q = query.strip().lower()
    rescored: list[tuple[float, dict]] = []
    for item in candidates:
        text = str(item.get("text", "")).lower()
        base = float(item.get("hybrid_score", 0.0))
        phrase_bonus = 0.2 if q and q in text else 0.0
        shortness_penalty = min(0.15, max(0.0, (len(text) - 1200) / 10000))
        final = base + phrase_bonus - shortness_penalty
        enriched = dict(item)
        enriched["rerank_score"] = round(final, 6)
        rescored.append((final, enriched))

    rescored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in rescored[: max(1, top_k)]]
