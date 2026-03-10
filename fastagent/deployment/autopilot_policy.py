from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class EnvironmentPolicy:
    environment: str
    promote_max_risk: float
    require_apply_success_for_promote: bool
    send_events: set[str]
    webhook_dry_run_default: bool


@dataclass
class PolicyEventDecision:
    event: str
    reason: str
    should_send: bool


_PRESETS: dict[str, EnvironmentPolicy] = {
    "dev": EnvironmentPolicy(
        environment="dev",
        promote_max_risk=0.9,
        require_apply_success_for_promote=False,
        send_events={"rollback_requested", "promotion_requested", "rollout_hold"},
        webhook_dry_run_default=True,
    ),
    "staging": EnvironmentPolicy(
        environment="staging",
        promote_max_risk=0.6,
        require_apply_success_for_promote=True,
        send_events={"rollback_requested", "promotion_requested", "rollout_hold"},
        webhook_dry_run_default=False,
    ),
    "prod": EnvironmentPolicy(
        environment="prod",
        promote_max_risk=0.35,
        require_apply_success_for_promote=True,
        send_events={"rollback_requested", "promotion_requested", "rollout_hold"},
        webhook_dry_run_default=False,
    ),
}


def load_environment_policy(environment: str, policy_file: Path | None = None) -> EnvironmentPolicy:
    normalized = environment.strip().lower() or "staging"
    if normalized not in _PRESETS:
        raise ValueError("Environment must be one of: dev, staging, prod")
    base = _PRESETS[normalized]
    if policy_file is None:
        return base

    if not policy_file.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_file}")
    try:
        payload = json.loads(policy_file.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid policy JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Policy file must be a JSON object")

    env_cfg = payload.get(normalized, {})
    if not isinstance(env_cfg, dict):
        raise ValueError(f"Policy entry for '{normalized}' must be an object")

    promote_max_risk = _to_float(env_cfg.get("promote_max_risk"), default=base.promote_max_risk, min_value=0.0, max_value=1.0)
    require_apply = _to_bool(env_cfg.get("require_apply_success_for_promote"), base.require_apply_success_for_promote)
    dry_run_default = _to_bool(env_cfg.get("webhook_dry_run_default"), base.webhook_dry_run_default)
    send_events_raw = env_cfg.get("send_events", sorted(base.send_events))
    send_events = _parse_send_events(send_events_raw)

    return EnvironmentPolicy(
        environment=normalized,
        promote_max_risk=promote_max_risk,
        require_apply_success_for_promote=require_apply,
        send_events=send_events,
        webhook_dry_run_default=dry_run_default,
    )


def decide_policy_event(
    policy: EnvironmentPolicy,
    decision: dict,
    apply_report: dict,
) -> PolicyEventDecision:
    action = str(decision.get("action", "hold")).strip().lower() or "hold"
    risk_score = float(decision.get("risk_score", 0.0))

    apply_enabled = bool(apply_report.get("enabled", False))
    apply_executed = bool(apply_report.get("executed", False))
    apply_status = int(apply_report.get("status_code", 0))
    apply_ok = apply_enabled and apply_executed and apply_status == 0

    if bool(decision.get("rollback_recommended", False)) or action == "rollback":
        event = "rollback_requested"
        reason = "rollback_recommended"
    elif action in {"advance", "complete"}:
        if risk_score > policy.promote_max_risk:
            event = "rollout_hold"
            reason = "promotion_blocked_by_policy_risk"
        elif policy.require_apply_success_for_promote and not apply_ok:
            event = "rollout_hold"
            reason = "promotion_blocked_by_policy_apply"
        else:
            event = "promotion_requested"
            reason = "promotion_allowed"
    else:
        event = "rollout_hold"
        reason = "rollout_held"

    return PolicyEventDecision(
        event=event,
        reason=reason,
        should_send=event in policy.send_events,
    )


def _to_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _to_float(value: object, default: float, min_value: float, max_value: float) -> float:
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, converted))


def _parse_send_events(value: object) -> set[str]:
    allowed = {"rollback_requested", "promotion_requested", "rollout_hold"}
    if not isinstance(value, list):
        return set(allowed)
    parsed: set[str] = set()
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text in allowed:
                parsed.add(text)
    return parsed or set(allowed)
