from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def _write_report(path: Path, accuracy: float, reasoning: float, hallucinations: float, cost: float) -> Path:
    path.write_text(
        json.dumps(
            {
                "metrics": {
                    "accuracy": accuracy,
                    "reasoning_quality": reasoning,
                    "hallucinations": hallucinations,
                    "cost": cost,
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def test_autopilot_advances_and_builds_apply_plan(tmp_path: Path) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.91, reasoning=0.91, hallucinations=0.1, cost=1.05)
    state_file = tmp_path / "rollout.state.json"
    output = tmp_path / "autopilot.json"

    result = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "simulate",
            "--simulate-count",
            "5",
            "--simulate-degradation",
            "0.0",
            "--max-latency-increase-ratio",
            "1.0",
            "--apply-provider",
            "argo",
            "--apply-resource",
            "my-rollout",
            "--output-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"]["action"] == "advance"
    assert payload["apply"]["enabled"] is True
    assert payload["apply"]["plan"]["target_weight"] == 5
    assert "argo rollouts set weight" in " ".join(payload["apply"]["plan"]["command"])


def test_autopilot_rolls_back_on_failed_canary(tmp_path: Path) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.7, reasoning=0.7, hallucinations=0.3, cost=2.0)
    state_file = tmp_path / "rollout.state.json"
    output = tmp_path / "autopilot_fail.json"

    result = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--output-json",
            str(output),
        ],
    )

    assert result.exit_code == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"]["action"] == "rollback"
    assert payload["state"]["status"] == "rollback_recommended"


def test_autopilot_webhook_dev_auto_mode_uses_dry_run(tmp_path: Path, monkeypatch) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.91, reasoning=0.9, hallucinations=0.1, cost=1.05)
    state_file = tmp_path / "rollout.state.json"
    output = tmp_path / "autopilot_webhook_dev.json"

    monkeypatch.setenv("FASTAGENT_DEPLOY_WEBHOOK_URL", "https://example.com/deploy-webhook")
    monkeypatch.setenv("FASTAGENT_DEPLOY_WEBHOOK_SECRET", "dev-secret")

    result = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--webhook",
            "--webhook-environment",
            "dev",
            "--webhook-mode",
            "auto",
            "--output-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["webhook"]["enabled"] is True
    assert payload["webhook"]["event"] == "promotion_requested"
    assert payload["webhook"]["dry_run"] is True
    assert payload["webhook"]["sent"] is False
    assert payload["webhook"]["signature"]


def test_autopilot_webhook_prod_blocks_promotion_by_risk(tmp_path: Path, monkeypatch) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.885, reasoning=0.87, hallucinations=0.1, cost=1.15)
    state_file = tmp_path / "rollout.state.json"
    output = tmp_path / "autopilot_webhook_prod.json"

    monkeypatch.setenv("FASTAGENT_DEPLOY_WEBHOOK_URL", "https://example.com/deploy-webhook")
    monkeypatch.setenv("FASTAGENT_DEPLOY_WEBHOOK_SECRET", "prod-secret")

    result = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--webhook",
            "--webhook-environment",
            "prod",
            "--webhook-mode",
            "dry-run",
            "--output-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["decision"]["action"] == "advance"
    assert payload["webhook"]["event"] == "rollout_hold"
    assert payload["webhook"]["reason"] == "promotion_blocked_by_policy_risk"
    assert payload["webhook"]["dry_run"] is True


def test_autopilot_approval_gate_pending_then_approved(tmp_path: Path) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.885, reasoning=0.87, hallucinations=0.1, cost=1.15)
    state_file = tmp_path / "rollout.state.json"
    approval_state = tmp_path / "rollout.approvals.json"
    output_pending = tmp_path / "autopilot_pending.json"

    pending = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--webhook-environment",
            "prod",
            "--output-json",
            str(output_pending),
        ],
    )
    assert pending.exit_code == 5
    pending_payload = json.loads(output_pending.read_text(encoding="utf-8"))
    request_id = pending_payload["approval"]["request_id"]
    assert request_id
    assert pending_payload["approval"]["status"] == "pending"

    resolved = runner.invoke(
        app,
        [
            "approval-resolve",
            "--state-file",
            str(approval_state),
            "--request-id",
            request_id,
            "--decision",
            "approve",
            "--approver",
            "ops-lead",
        ],
    )
    assert resolved.exit_code == 0

    output_approved = tmp_path / "autopilot_approved.json"
    approved = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--approval-request-id",
            request_id,
            "--webhook-environment",
            "prod",
            "--output-json",
            str(output_approved),
        ],
    )
    assert approved.exit_code == 0
    approved_payload = json.loads(output_approved.read_text(encoding="utf-8"))
    assert approved_payload["approval"]["status"] == "approved"
    assert approved_payload["approval"]["reason"] == "manual_approval_override"


def test_autopilot_approval_gate_rejected_exits_6(tmp_path: Path) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.885, reasoning=0.87, hallucinations=0.1, cost=1.15)
    state_file = tmp_path / "rollout.state.json"
    approval_state = tmp_path / "rollout.approvals.json"
    output_pending = tmp_path / "autopilot_pending.json"

    pending = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--webhook-environment",
            "prod",
            "--output-json",
            str(output_pending),
        ],
    )
    assert pending.exit_code == 5
    request_id = json.loads(output_pending.read_text(encoding="utf-8"))["approval"]["request_id"]

    reject = runner.invoke(
        app,
        [
            "approval-resolve",
            "--state-file",
            str(approval_state),
            "--request-id",
            request_id,
            "--decision",
            "reject",
            "--approver",
            "ops-lead",
        ],
    )
    assert reject.exit_code == 0

    output_rejected = tmp_path / "autopilot_rejected.json"
    rejected = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--approval-request-id",
            request_id,
            "--webhook-environment",
            "prod",
            "--output-json",
            str(output_rejected),
        ],
    )
    assert rejected.exit_code == 6


def test_autopilot_approval_expired_escalates_dry_run(tmp_path: Path) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.885, reasoning=0.87, hallucinations=0.1, cost=1.15)
    state_file = tmp_path / "rollout.state.json"
    approval_state = tmp_path / "rollout.approvals.json"
    output_pending = tmp_path / "autopilot_pending.json"

    pending = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--approval-ttl-minutes",
            "60",
            "--webhook-environment",
            "prod",
            "--output-json",
            str(output_pending),
        ],
    )
    assert pending.exit_code == 5
    pending_payload = json.loads(output_pending.read_text(encoding="utf-8"))
    request_id = pending_payload["approval"]["request_id"]

    state_payload = json.loads(approval_state.read_text(encoding="utf-8"))
    state_payload["requests"][0]["expires_at"] = "2000-01-01T00:00:00+00:00"
    approval_state.write_text(json.dumps(state_payload), encoding="utf-8")

    output_expired = tmp_path / "autopilot_expired.json"
    expired = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--approval-request-id",
            request_id,
            "--approval-escalation-url",
            "https://hooks.slack.com/services/a/b/c",
            "--approval-escalation-mode",
            "dry-run",
            "--webhook-environment",
            "prod",
            "--output-json",
            str(output_expired),
        ],
    )
    assert expired.exit_code == 7
    payload = json.loads(output_expired.read_text(encoding="utf-8"))
    assert payload["approval"]["status"] == "expired"
    assert payload["approval"]["escalation"]["status"] == "dry_run"
    assert payload["approval"]["escalation"]["channel"] == "slack"
    assert payload["approval"]["escalation"]["attempted"] is True


def test_autopilot_approval_escalation_dedupes_same_incident(tmp_path: Path) -> None:
    baseline = _write_report(tmp_path / "baseline.json", accuracy=0.9, reasoning=0.9, hallucinations=0.1, cost=1.0)
    candidate = _write_report(tmp_path / "candidate.json", accuracy=0.885, reasoning=0.87, hallucinations=0.1, cost=1.15)
    state_file = tmp_path / "rollout.state.json"
    approval_state = tmp_path / "rollout.approvals.json"
    output_pending = tmp_path / "autopilot_pending.json"

    pending = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--approval-ttl-minutes",
            "60",
            "--webhook-environment",
            "prod",
            "--output-json",
            str(output_pending),
        ],
    )
    assert pending.exit_code == 5
    pending_payload = json.loads(output_pending.read_text(encoding="utf-8"))
    request_id = pending_payload["approval"]["request_id"]

    state_payload = json.loads(approval_state.read_text(encoding="utf-8"))
    state_payload["requests"][0]["expires_at"] = "2000-01-01T00:00:00+00:00"
    approval_state.write_text(json.dumps(state_payload), encoding="utf-8")

    first_output = tmp_path / "autopilot_expired_first.json"
    first = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--approval-request-id",
            request_id,
            "--approval-escalation-urls",
            "https://hooks.slack.com/services/a/b/c,https://outlook.office.com/webhook/abc",
            "--approval-escalation-mode",
            "dry-run",
            "--approval-escalation-cooldown-minutes",
            "1",
            "--webhook-environment",
            "prod",
            "--output-json",
            str(first_output),
        ],
    )
    assert first.exit_code == 7

    state_payload = json.loads(approval_state.read_text(encoding="utf-8"))
    state_payload["requests"][0]["last_escalated_at"] = "2000-01-01T00:00:00+00:00"
    approval_state.write_text(json.dumps(state_payload), encoding="utf-8")

    second_output = tmp_path / "autopilot_expired_second.json"
    second = runner.invoke(
        app,
        [
            "autopilot",
            "--baseline-report",
            str(baseline),
            "--candidate-report",
            str(candidate),
            "--state-file",
            str(state_file),
            "--shadow-mode",
            "none",
            "--approval-gate",
            "--approval-state-file",
            str(approval_state),
            "--approval-request-id",
            request_id,
            "--approval-escalation-urls",
            "https://hooks.slack.com/services/a/b/c,https://outlook.office.com/webhook/abc",
            "--approval-escalation-mode",
            "dry-run",
            "--approval-escalation-cooldown-minutes",
            "1",
            "--webhook-environment",
            "prod",
            "--output-json",
            str(second_output),
        ],
    )
    assert second.exit_code == 7
    second_payload = json.loads(second_output.read_text(encoding="utf-8"))
    esc = second_payload["approval"]["escalation"]
    assert esc["status"] == "skipped_deduped"
    assert esc["deduped"] >= 2
