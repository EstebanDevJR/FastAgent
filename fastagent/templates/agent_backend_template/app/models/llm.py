from app.config.settings import settings
from app.models.router import ModelRouter


class LLMClient:
    def __init__(self, provider: str = "OpenAI") -> None:
        self.provider = provider
        providers = [item.strip() for item in settings.router_providers.split(",") if item.strip()]
        self.router = ModelRouter(mode=settings.router_mode, providers=providers)

    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        history = context or []
        selected = self.router.select_provider(self.provider)

        # Demo fallback path for observability/testing.
        if "[force_fail]" in prompt.lower():
            fallback = self.router.fallback_provider(selected)
            return f"[{fallback}] fallback_after_failure | prompt={prompt} | history={len(history)}"

        return f"[{selected}] {prompt} | history={len(history)} | router_mode={self.router.mode}"
