class Retriever:
    def __init__(self, vector_db: str = "None") -> None:
        self.vector_db = vector_db
        self._documents: list[str] = []

    def index(self, text: str) -> None:
        self._documents.append(text)

    def retrieve(self, query: str, top_k: int = 3) -> list[str]:
        if self.vector_db.lower() == "none":
            return []
        return [doc for doc in self._documents if query.lower() in doc.lower()][:top_k] or [
            "No indexed documents yet."
        ]
