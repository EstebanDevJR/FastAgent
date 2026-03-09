class LLMClient:
    def __init__(self, provider: str = "OpenAI") -> None:
        self.provider = provider

    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        history = context or []
        return f"[{self.provider}] {prompt} | history={len(history)}"
