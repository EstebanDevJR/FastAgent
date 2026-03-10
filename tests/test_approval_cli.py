from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def _seed_state(path: Path) -> None:
    payload = {
        "requests": [
            {
                "id": "apr-20260310-000001-001",
                "status": "pending",
                "created_at": "2026-03-10T00:00:00+00:00",
                "updated_at": "2026-03-10T00:00:00+00:00",
                "deployment_id": "dep-1",
                "environment": "prod",
                "reason": "promotion_blocked_by_policy_risk",
                "current_phase": 25,
                "next_phase": 50,
                "risk_score": 0.6,
                "decision": {"action": "advance"},
                "apply": {"enabled": True, "executed": False, "status_code": 0},
                "canary_passed": True,
                "shadow_passed": True,
                "approver": "",
                "notes": "",
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_approval_list_and_resolve(tmp_path: Path) -> None:
    state = tmp_path / "rollout.approvals.json"
    _seed_state(state)
    out = tmp_path / "approval.json"

    list_result = runner.invoke(
        app,
        [
            "approval-list",
            "--state-file",
            str(state),
        ],
    )
    assert list_result.exit_code == 0
    assert "dep-1" in list_result.stdout

    resolve_result = runner.invoke(
        app,
        [
            "approval-resolve",
            "--state-file",
            str(state),
            "--request-id",
            "apr-20260310-000001-001",
            "--decision",
            "approve",
            "--approver",
            "qa-lead",
            "--output-json",
            str(out),
        ],
    )
    assert resolve_result.exit_code == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "approved"
    assert payload["approver"] == "qa-lead"
