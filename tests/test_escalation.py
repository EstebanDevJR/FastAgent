from fastagent.deployment.escalation import build_escalation_payload, detect_channel


def test_detect_channel_auto() -> None:
    assert detect_channel("https://hooks.slack.com/services/a/b/c", channel="auto") == "slack"
    assert detect_channel("https://outlook.office.com/webhook/abc", channel="auto") == "teams"
    assert detect_channel("https://example.com/webhook", channel="auto") == "generic"


def test_build_escalation_payload_shapes() -> None:
    request = {
        "id": "apr-1",
        "reason": "approval_sla_expired",
        "current_phase": 25,
        "next_phase": 50,
        "expires_at": "2026-03-10T10:00:00+00:00",
    }
    slack = build_escalation_payload("slack", "dep-1", "prod", request, "rollout.approvals.json")
    teams = build_escalation_payload("teams", "dep-1", "prod", request, "rollout.approvals.json")
    generic = build_escalation_payload("generic", "dep-1", "prod", request, "rollout.approvals.json")

    assert "text" in slack
    assert "text" in teams
    assert generic["event"] == "approval_escalation"
    assert generic["request_id"] == "apr-1"
