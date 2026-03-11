from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
import time

from app.config.settings import settings


@dataclass
class PluginPolicyDecision:
    allowed: bool
    reason: str = "allowed"


class PluginExecutionPolicy:
    def __init__(
        self,
        enabled: bool = True,
        allowed: list[str] | None = None,
        denied: list[str] | None = None,
        max_calls_per_request: int = 3,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.enabled = enabled
        self.allowed = {item.strip().lower() for item in (allowed or []) if item.strip()}
        self.denied = {item.strip().lower() for item in (denied or []) if item.strip()}
        self.max_calls_per_request = max(1, max_calls_per_request)
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(1.0, cooldown_seconds)

        self._request_calls: ContextVar[int] = ContextVar("plugin_request_calls", default=0)
        self._failures: dict[str, int] = {}
        self._open_until: dict[str, float] = {}

    def start_request(self) -> Token[int]:
        return self._request_calls.set(0)

    def end_request(self, token: Token[int]) -> None:
        self._request_calls.reset(token)

    def can_execute(self, plugin_name: str) -> PluginPolicyDecision:
        if not self.enabled:
            return PluginPolicyDecision(allowed=True, reason="policy_disabled")

        normalized = plugin_name.strip().lower()
        if self.allowed and normalized not in self.allowed:
            return PluginPolicyDecision(allowed=False, reason="not_in_allowlist")
        if normalized in self.denied:
            return PluginPolicyDecision(allowed=False, reason="in_denylist")

        current_calls = self._request_calls.get()
        if current_calls >= self.max_calls_per_request:
            return PluginPolicyDecision(allowed=False, reason="max_calls_per_request_exceeded")

        now = time.time()
        open_until = self._open_until.get(normalized, 0.0)
        if open_until > now:
            return PluginPolicyDecision(allowed=False, reason="circuit_open")

        return PluginPolicyDecision(allowed=True, reason="allowed")

    def register_call(self) -> None:
        current = self._request_calls.get()
        self._request_calls.set(current + 1)

    def register_success(self, plugin_name: str) -> None:
        normalized = plugin_name.strip().lower()
        self._failures[normalized] = 0
        self._open_until.pop(normalized, None)

    def register_failure(self, plugin_name: str) -> None:
        normalized = plugin_name.strip().lower()
        failures = self._failures.get(normalized, 0) + 1
        self._failures[normalized] = failures
        if failures >= self.failure_threshold:
            self._open_until[normalized] = time.time() + self.cooldown_seconds
            self._failures[normalized] = 0

    def status_summary(self) -> dict:
        now = time.time()
        open_plugins = {
            name: round(until - now, 3)
            for name, until in self._open_until.items()
            if until > now
        }
        return {
            "enabled": self.enabled,
            "allowed_count": len(self.allowed),
            "denied_count": len(self.denied),
            "max_calls_per_request": self.max_calls_per_request,
            "failure_threshold": self.failure_threshold,
            "cooldown_seconds": self.cooldown_seconds,
            "open_circuits": open_plugins,
        }


def _csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


_POLICY = PluginExecutionPolicy(
    enabled=settings.plugin_policy_enabled,
    allowed=_csv_to_list(settings.plugin_allowed),
    denied=_csv_to_list(settings.plugin_denied),
    max_calls_per_request=settings.plugin_max_calls_per_request,
    failure_threshold=settings.plugin_circuit_failure_threshold,
    cooldown_seconds=settings.plugin_circuit_cooldown_seconds,
)


def get_plugin_policy() -> PluginExecutionPolicy:
    return _POLICY
