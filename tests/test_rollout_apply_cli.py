from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def _decision_report(path: Path, action: str = "advance", current_phase: int = 25, next_phase: int = 50) -> Path:
    payload = {
        "decision": {
            "action": action,
            "current_phase": current_phase,
            "next_phase": next_phase,
            "passed": action != "rollback",
            "rollback_recommended": action == "rollback",
        },
        "state": {"current_phase": current_phase},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_rollout_apply_argo_dry_run(tmp_path: Path) -> None:
    report = _decision_report(tmp_path / "rollout_decision.json", action="advance", current_phase=25, next_phase=50)
    output = tmp_path / "apply.json"
    result = runner.invoke(
        app,
        [
            "rollout-apply",
            "--decision-report",
            str(report),
            "--provider",
            "argo",
            "--resource",
            "my-rollout",
            "--output-json",
            str(output),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["plan"]["target_weight"] == 50
    assert "argo rollouts set weight" in " ".join(payload["plan"]["command"])


def test_rollout_apply_gateway_rollback_weight_zero(tmp_path: Path) -> None:
    report = _decision_report(tmp_path / "rollout_decision.json", action="rollback", current_phase=25, next_phase=25)
    output = tmp_path / "gateway_apply.json"
    result = runner.invoke(
        app,
        [
            "rollout-apply",
            "--decision-report",
            str(report),
            "--provider",
            "gateway",
            "--resource",
            "my-route",
            "--baseline-backend",
            "stable-svc",
            "--candidate-backend",
            "canary-svc",
            "--output-json",
            str(output),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    patch = payload["plan"]["patch"]
    assert patch["spec"]["rules"][0]["backendRefs"][0]["weight"] == 100
    assert patch["spec"]["rules"][0]["backendRefs"][1]["weight"] == 0
