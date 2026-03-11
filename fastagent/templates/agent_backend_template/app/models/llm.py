from app.config.settings import settings
from app.models.cost_guard import CostGuard
from app.models.providers import (
    AnthropicProvider,
    GoogleGeminiProvider,
    LLMProvider,
    LocalReasoningProvider,
    OllamaProvider,
    OpenAIProvider,
    ProviderError,
)
from app.models.router import ModelRouter


class LLMClient:
    def __init__(self, provider: str = "OpenAI") -> None:
        self.provider = provider
        providers = [item.strip() for item in settings.router_providers.split(",") if item.strip()]
        self.router = ModelRouter(mode=settings.router_mode, providers=providers)
        self.cost_guard = CostGuard(
            enabled=settings.cost_guard_enabled,
            cost_per_1k_tokens_usd=settings.cost_per_1k_tokens_usd,
            session_budget_usd=settings.cost_session_budget_usd,
            global_budget_usd=settings.cost_global_budget_usd,
            block_on_budget=settings.cost_block_on_budget,
            alert_threshold=settings.cost_alert_threshold,
        )
        self.allow_local_fallback = settings.llm_allow_local_fallback
        self.local_provider: LLMProvider = LocalReasoningProvider()
        self.providers: dict[str, LLMProvider] = {
            "OpenAI": OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                base_url=settings.openai_base_url,
                timeout=settings.llm_request_timeout,
            ),
            "Anthropic": AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.anthropic_model,
                base_url=settings.anthropic_base_url,
                timeout=settings.llm_request_timeout,
            ),
            "Google DeepMind": GoogleGeminiProvider(
                api_key=settings.google_api_key,
                model=settings.google_model,
                base_url=settings.google_base_url,
                timeout=settings.llm_request_timeout,
            ),
            "Meta AI": OllamaProvider(
                model=settings.meta_model,
                base_url=settings.ollama_base_url,
                timeout=settings.llm_request_timeout,
            ),
            "Local": self.local_provider,
        }

    def generate(self, prompt: str, context: list[str] | None = None, session_id: str | None = None) -> str:
        history = context or []
        sid = session_id or "default"

        estimated_input_cost = self.cost_guard.estimate_cost(prompt=prompt, history=history)
        decision = self.cost_guard.can_spend(sid, estimated_input_cost)
        if not decision.allowed:
            return f"blocked_by_cost_guard:{decision.reason}"

        selected = self.router.select_provider(self.provider)
        candidates = self._candidate_order(selected)
        response = ""
        errors: list[str] = []

        for candidate in candidates:
            provider_client = self.providers.get(candidate)
            if provider_client is None:
                errors.append(f"{candidate}: provider not configured")
                continue
            try:
                response = provider_client.generate(prompt=prompt, context=history).strip()
            except ProviderError as exc:
                errors.append(f"{candidate}: {exc}")
                continue
            if response:
                break

        if not response and self.allow_local_fallback:
            response = self.local_provider.generate(prompt=prompt, context=history).strip()

        if not response:
            response = "provider_error: " + " | ".join(errors[:3])

        total_cost = estimated_input_cost + self.cost_guard.estimate_response_cost(response)
        self.cost_guard.register_spend(sid, total_cost)
        return response

    def cost_status(self, session_id: str | None = None) -> dict:
        return self.cost_guard.status(session_id=session_id)

    def _candidate_order(self, selected: str) -> list[str]:
        ordered: list[str] = []
        if selected:
            ordered.append(selected)

        fallback = self.router.fallback_provider(selected)
        if fallback and fallback not in ordered:
            ordered.append(fallback)

        for provider_name in self.providers:
            if provider_name == "Local":
                continue
            if provider_name not in ordered:
                ordered.append(provider_name)

        if "Local" not in ordered:
            ordered.append("Local")
        return ordered
