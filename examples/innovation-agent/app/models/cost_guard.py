from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostDecision:
    allowed: bool
    estimated_cost: float
    reason: str


class CostGuard:
    def __init__(
        self,
        enabled: bool = True,
        cost_per_1k_tokens_usd: float = 0.002,
        session_budget_usd: float = 0.05,
        global_budget_usd: float = 10.0,
        block_on_budget: bool = True,
        alert_threshold: float = 0.8,
    ) -> None:
        self.enabled = enabled
        self.cost_per_1k_tokens_usd = max(0.000001, float(cost_per_1k_tokens_usd))
        self.session_budget_usd = max(0.0, float(session_budget_usd))
        self.global_budget_usd = max(0.0, float(global_budget_usd))
        self.block_on_budget = block_on_budget
        self.alert_threshold = min(1.0, max(0.0, float(alert_threshold)))

        self._session_spend: dict[str, float] = {}
        self._global_spend: float = 0.0

    def estimate_cost(self, prompt: str, history: list[str] | None = None) -> float:
        text = prompt + " " + " ".join(history or [])
        token_estimate = max(1, len(text) // 4)
        return round((token_estimate / 1000.0) * self.cost_per_1k_tokens_usd, 6)

    def estimate_response_cost(self, response: str) -> float:
        token_estimate = max(1, len(response) // 4)
        return round((token_estimate / 1000.0) * self.cost_per_1k_tokens_usd, 6)

    def can_spend(self, session_id: str, estimated_cost: float) -> CostDecision:
        if not self.enabled:
            return CostDecision(allowed=True, estimated_cost=estimated_cost, reason="disabled")

        session_spend = self._session_spend.get(session_id, 0.0)
        projected_session = session_spend + estimated_cost
        projected_global = self._global_spend + estimated_cost

        if self.session_budget_usd > 0 and projected_session > self.session_budget_usd:
            return CostDecision(allowed=not self.block_on_budget, estimated_cost=estimated_cost, reason="session_budget_exceeded")
        if self.global_budget_usd > 0 and projected_global > self.global_budget_usd:
            return CostDecision(allowed=not self.block_on_budget, estimated_cost=estimated_cost, reason="global_budget_exceeded")

        return CostDecision(allowed=True, estimated_cost=estimated_cost, reason="allowed")

    def register_spend(self, session_id: str, cost: float) -> None:
        if cost <= 0:
            return
        self._session_spend[session_id] = round(self._session_spend.get(session_id, 0.0) + cost, 6)
        self._global_spend = round(self._global_spend + cost, 6)

    def status(self, session_id: str | None = None) -> dict:
        sid = session_id or "default"
        session_spend = self._session_spend.get(sid, 0.0)
        session_ratio = (session_spend / self.session_budget_usd) if self.session_budget_usd > 0 else 0.0
        global_ratio = (self._global_spend / self.global_budget_usd) if self.global_budget_usd > 0 else 0.0
        return {
            "enabled": self.enabled,
            "block_on_budget": self.block_on_budget,
            "cost_per_1k_tokens_usd": self.cost_per_1k_tokens_usd,
            "session_budget_usd": self.session_budget_usd,
            "global_budget_usd": self.global_budget_usd,
            "session_id": sid,
            "session_spend_usd": round(session_spend, 6),
            "global_spend_usd": round(self._global_spend, 6),
            "session_usage_ratio": round(session_ratio, 4),
            "global_usage_ratio": round(global_ratio, 4),
            "session_alert": session_ratio >= self.alert_threshold if self.session_budget_usd > 0 else False,
            "global_alert": global_ratio >= self.alert_threshold if self.global_budget_usd > 0 else False,
        }
