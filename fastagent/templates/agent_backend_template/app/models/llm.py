from app.config.settings import settings
from app.models.cost_guard import CostGuard
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

    def generate(self, prompt: str, context: list[str] | None = None, session_id: str | None = None) -> str:
        history = context or []
        sid = session_id or "default"

        estimated_input_cost = self.cost_guard.estimate_cost(prompt=prompt, history=history)
        decision = self.cost_guard.can_spend(sid, estimated_input_cost)
        if not decision.allowed:
            return f"blocked_by_cost_guard:{decision.reason}"

        selected = self.router.select_provider(self.provider)

        # Demo fallback path for observability/testing.
        if "[force_fail]" in prompt.lower():
            fallback = self.router.fallback_provider(selected)
            response = f"[{fallback}] fallback_after_failure | prompt={prompt} | history={len(history)}"
        else:
            response = f"[{selected}] {prompt} | history={len(history)} | router_mode={self.router.mode}"

        total_cost = estimated_input_cost + self.cost_guard.estimate_response_cost(response)
        self.cost_guard.register_spend(sid, total_cost)
        return response

    def cost_status(self, session_id: str | None = None) -> dict:
        return self.cost_guard.status(session_id=session_id)
