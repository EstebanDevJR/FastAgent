from pathlib import Path
import json

from fastagent.deployment.autopilot_policy import decide_policy_event, load_environment_policy


def test_load_environment_policy_defaults() -> None:
    dev = load_environment_policy("dev")
    prod = load_environment_policy("prod")

    assert dev.environment == "dev"
    assert dev.webhook_dry_run_default is True
    assert prod.environment == "prod"
    assert prod.promote_max_risk == 0.35


def test_load_environment_policy_override_file(tmp_path: Path) -> None:
    policy_file = tmp_path / "policy.json"
    policy_file.write_text(
        json.dumps(
            {
                "staging": {
                    "promote_max_risk": 0.5,
                    "require_apply_success_for_promote": False,
                    "webhook_dry_run_default": True,
                    "send_events": ["rollback_requested", "promotion_requested"],
                }
            }
        ),
        encoding="utf-8",
    )

    policy = load_environment_policy("staging", policy_file=policy_file)
    assert policy.promote_max_risk == 0.5
    assert policy.require_apply_success_for_promote is False
    assert policy.webhook_dry_run_default is True
    assert "rollout_hold" not in policy.send_events


def test_decide_policy_event_blocks_promotion_if_apply_required() -> None:
    policy = load_environment_policy("staging")
    decision = {"action": "advance", "risk_score": 0.2, "rollback_recommended": False}
    apply_report = {"enabled": False, "executed": False, "status_code": 0}

    policy_decision = decide_policy_event(policy, decision=decision, apply_report=apply_report)

    assert policy_decision.event == "rollout_hold"
    assert policy_decision.reason == "promotion_blocked_by_policy_apply"
    assert policy_decision.should_send is True
