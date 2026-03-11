from __future__ import annotations

import hashlib


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> list[str]:
    value = text.strip()
    if not value:
        return []
    if chunk_size <= 0:
        return [value]

    chunks: list[str] = []
    start = 0
    n = len(value)
    step = max(1, chunk_size - max(0, overlap))
    while start < n:
        end = min(n, start + chunk_size)
        chunks.append(value[start:end].strip())
        if end >= n:
            break
        start += step
    return [item for item in chunks if item]


def dedupe_chunks(chunks: list[str]) -> list[str]:
    seen = set()
    unique: list[str] = []
    for chunk in chunks:
        digest = hashlib.sha1(chunk.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(chunk)
    return unique
