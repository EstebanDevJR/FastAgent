from dataclasses import dataclass


@dataclass
class ProviderProfile:
    name: str
    quality: float
    latency_ms: float
    cost_per_1k_tokens: float


PROFILES = {
    "OpenAI": ProviderProfile("OpenAI", quality=0.95, latency_ms=900, cost_per_1k_tokens=0.03),
    "Anthropic": ProviderProfile("Anthropic", quality=0.93, latency_ms=950, cost_per_1k_tokens=0.028),
    "Google DeepMind": ProviderProfile("Google DeepMind", quality=0.92, latency_ms=850, cost_per_1k_tokens=0.02),
    "Meta AI": ProviderProfile("Meta AI", quality=0.87, latency_ms=700, cost_per_1k_tokens=0.005),
}


class ModelRouter:
    def __init__(self, mode: str = "balanced", providers: list[str] | None = None) -> None:
        self.mode = (mode or "balanced").strip().lower()
        self.providers = providers or list(PROFILES.keys())
        self.providers = [p for p in self.providers if p in PROFILES] or list(PROFILES.keys())

    def _score(self, profile: ProviderProfile) -> float:
        if self.mode == "quality":
            return profile.quality
        if self.mode == "latency":
            return 1.0 / max(profile.latency_ms, 1)
        if self.mode == "cost":
            return 1.0 / max(profile.cost_per_1k_tokens, 0.000001)

        # balanced
        quality_score = profile.quality
        latency_score = 1.0 / max(profile.latency_ms, 1)
        cost_score = 1.0 / max(profile.cost_per_1k_tokens, 0.000001)
        return (0.5 * quality_score) + (0.25 * latency_score * 1000) + (0.25 * cost_score * 0.01)

    def select_provider(self, preferred_provider: str | None = None) -> str:
        if preferred_provider in self.providers:
            return preferred_provider
        ranked = sorted(self.providers, key=lambda p: self._score(PROFILES[p]), reverse=True)
        return ranked[0]

    def fallback_provider(self, current: str) -> str:
        alternatives = [provider for provider in self.providers if provider != current]
        if not alternatives:
            return current
        ranked = sorted(alternatives, key=lambda p: self._score(PROFILES[p]), reverse=True)
        return ranked[0]

