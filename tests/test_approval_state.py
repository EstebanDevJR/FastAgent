from pathlib import Path

from fastagent.deployment.approval import (
    get_or_create_pending_request,
    is_request_expired,
    load_approval_state,
    mark_request_expired,
    record_request_escalation,
    should_escalate_request,
)


def test_pending_request_contains_sla_fields(tmp_path: Path) -> None:
    state = load_approval_state(path=tmp_path / "missing.approvals.json")
    req = get_or_create_pending_request(
        state=state,
        deployment_id="dep-1",
        environment="prod",
        reason="policy_hold",
        decision={"current_phase": 25, "next_phase": 50, "risk_score": 0.61},
        apply_report={"enabled": True, "executed": False, "status_code": 0},
        canary_payload={"passed": True},
        shadow_payload={"summary": {"passed": True}},
        ttl_minutes=30,
    )
    assert req["ttl_minutes"] == 30
    assert req["expires_at"]
    assert req["status"] == "pending"
    assert req["escalation_count"] == 0


def test_expire_and_escalation_tracking() -> None:
    request = {
        "id": "apr-test-1",
        "status": "pending",
        "created_at": "2025-01-01T00:00:00+00:00",
        "expires_at": "2025-01-01T00:01:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
        "escalation_count": 0,
    }
    assert is_request_expired(request) is True
    request = mark_request_expired(request, notes="sla")
    assert request["status"] == "expired"
    assert should_escalate_request(request, cooldown_minutes=60) is True
    request = record_request_escalation(
        request=request,
        channel="slack",
        url="https://hooks.slack.com/services/a/b/c",
        dry_run=True,
        attempted=True,
        sent=False,
        status_code=0,
    )
    assert request["escalation_count"] == 1
    assert should_escalate_request(request, cooldown_minutes=60) is False
