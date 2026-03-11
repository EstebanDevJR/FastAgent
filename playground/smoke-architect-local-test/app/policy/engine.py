from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str = ""
    matched_rule: str = ""


class PolicyEngine:
    def __init__(self, enabled: bool = True, policy_file: str = "app/policy/policies.json") -> None:
        self.enabled = enabled
        self.policy_file = Path(policy_file)
        self.rules: list[dict] = []
        self.load_error: str = ""
        self._load_rules()

    def _load_rules(self) -> None:
        if not self.policy_file.exists():
            self.rules = []
            return
        try:
            payload = json.loads(self.policy_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.rules = []
            self.load_error = str(exc)
            return

        if isinstance(payload, dict) and isinstance(payload.get("rules"), list):
            self.rules = [item for item in payload["rules"] if isinstance(item, dict)]
        else:
            self.rules = []

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    def evaluate(self, message: str, session_id: str | None = None) -> PolicyDecision:
        if not self.enabled:
            return PolicyDecision(allowed=True, reason="policy_disabled")

        text = str(message or "")
        for idx, rule in enumerate(self.rules, start=1):
            name = str(rule.get("name", f"rule_{idx}"))
            rule_type = str(rule.get("type", "")).strip().lower()

            if rule_type == "deny_regex":
                pattern = str(rule.get("pattern", "")).strip()
                if pattern and re.search(pattern, text):
                    return PolicyDecision(allowed=False, reason="message denied by regex", matched_rule=name)

            if rule_type == "max_length":
                value = int(rule.get("value", 0))
                if value > 0 and len(text) > value:
                    return PolicyDecision(allowed=False, reason=f"message length exceeds {value}", matched_rule=name)

            if rule_type == "deny_prefix":
                prefix = str(rule.get("value", "")).strip().lower()
                if prefix and text.strip().lower().startswith(prefix):
                    return PolicyDecision(allowed=False, reason="message denied by prefix", matched_rule=name)

        return PolicyDecision(allowed=True, reason="allowed", matched_rule="")
