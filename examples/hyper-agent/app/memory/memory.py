class BaseMemory:
    def store(self, session_id: str, message: str) -> None:
        raise NotImplementedError

    def recall(self, session_id: str) -> list[str]:
        raise NotImplementedError


class ConversationMemory(BaseMemory):
    def __init__(self) -> None:
        self._messages: dict[str, list[str]] = {}

    def store(self, session_id: str, message: str) -> None:
        self._messages.setdefault(session_id, []).append(message)

    def recall(self, session_id: str) -> list[str]:
        return list(self._messages.get(session_id, []))


class VectorMemory(ConversationMemory):
    pass


class HybridMemory(ConversationMemory):
    pass


def get_memory(memory_type: str) -> BaseMemory:
    if memory_type == "vector":
        return VectorMemory()
    if memory_type == "hybrid":
        return HybridMemory()
    return ConversationMemory()
