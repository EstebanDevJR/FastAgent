from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Protocol

from app.config.settings import settings


class BaseMemory(Protocol):
    def store(self, session_id: str, message: str) -> None:
        ...

    def recall(self, session_id: str, query: str | None = None, top_k: int | None = None) -> list[str]:
        ...


class ConversationMemory(BaseMemory):
    def __init__(self) -> None:
        self._messages: dict[str, list[str]] = {}

    def store(self, session_id: str, message: str) -> None:
        self._messages.setdefault(session_id, []).append(message)

    def recall(self, session_id: str, query: str | None = None, top_k: int | None = None) -> list[str]:
        _ = query
        _ = top_k
        return list(self._messages.get(session_id, []))


@dataclass
class MemoryRecord:
    message: str
    embedding: list[float]
    position: int


class VectorMemory(BaseMemory):
    def __init__(self, dimensions: int | None = None, default_top_k: int | None = None, max_messages: int = 2000) -> None:
        self.dimensions = max(16, dimensions or settings.memory_vector_dimensions)
        self.default_top_k = max(1, default_top_k or settings.memory_vector_top_k)
        self.max_messages = max(50, max_messages)
        self._records: dict[str, list[MemoryRecord]] = {}

    def store(self, session_id: str, message: str) -> None:
        items = self._records.setdefault(session_id, [])
        items.append(
            MemoryRecord(
                message=message,
                embedding=_embed_text(message, self.dimensions),
                position=len(items),
            )
        )
        if len(items) > self.max_messages:
            del items[: len(items) - self.max_messages]

    def recall(self, session_id: str, query: str | None = None, top_k: int | None = None) -> list[str]:
        records = self._records.get(session_id, [])
        if not records:
            return []

        limit = max(1, top_k or self.default_top_k)
        if not query or not query.strip():
            return [item.message for item in records[-limit:]]

        query_embedding = _embed_text(query, self.dimensions)
        scored = sorted(
            records,
            key=lambda item: (_cosine_similarity(query_embedding, item.embedding), item.position),
            reverse=True,
        )
        selected = scored[:limit]
        selected_sorted = sorted(selected, key=lambda item: item.position)
        return [item.message for item in selected_sorted]


class HybridMemory(VectorMemory):
    def __init__(self, dimensions: int | None = None, default_top_k: int | None = None, recency_window: int | None = None) -> None:
        super().__init__(dimensions=dimensions, default_top_k=default_top_k)
        self.recency_window = max(1, recency_window or settings.memory_recency_window)

    def recall(self, session_id: str, query: str | None = None, top_k: int | None = None) -> list[str]:
        records = self._records.get(session_id, [])
        if not records:
            return []

        recent = [item.message for item in records[-self.recency_window :]]
        semantic = super().recall(session_id=session_id, query=query, top_k=top_k)

        merged: list[str] = []
        seen: set[str] = set()
        for item in recent + semantic:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
        return merged


def get_memory(memory_type: str) -> BaseMemory:
    if memory_type == "vector":
        return VectorMemory()
    if memory_type == "hybrid":
        return HybridMemory()
    return ConversationMemory()


def _embed_text(text: str, dimensions: int) -> list[float]:
    values = [0.0] * dimensions
    tokens = _tokenize(text)
    if not tokens:
        return values

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], byteorder="big", signed=False) % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        weight = 1.0 + (digest[3] / 255.0)
        values[bucket] += sign * weight

    norm = math.sqrt(sum(item * item for item in values))
    if norm > 0:
        values = [item / norm for item in values]
    return values


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def _tokenize(text: str) -> list[str]:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return []

    tokens: list[str] = []
    current: list[str] = []
    for char in normalized:
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))

    if len(tokens) < 2:
        return tokens

    bigrams = [f"{tokens[idx]}_{tokens[idx + 1]}" for idx in range(len(tokens) - 1)]
    return tokens + bigrams
