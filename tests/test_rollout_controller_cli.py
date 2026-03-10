from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def test_rollout_controller_advances_phase(tmp_path: Path) -> None:
    canary = tmp_path / "canary.json"
    shadow = tmp_path / "shadow.json"
    state_file = tmp_path / "rollout.state.json"
    canary.write_text(json.dumps({"passed": True}), encoding="utf-8")
    shadow.write_text(json.dumps({"summary": {"passed": True}}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "rollout-controller",
            "--state-file",
            str(state_file),
            "--canary-report",
            str(canary),
            "--shadow-report",
            str(shadow),
            "--phase-plan",
            "5,25,50,100",
        ],
    )
    assert result.exit_code == 0
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["current_phase"] == 5
    assert state["status"].startswith("advanced_to_")


def test_rollout_controller_recommends_rollback(tmp_path: Path) -> None:
    canary = tmp_path / "canary_fail.json"
    state_file = tmp_path / "rollout.state.json"
    canary.write_text(json.dumps({"passed": False}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "rollout-controller",
            "--state-file",
            str(state_file),
            "--canary-report",
            str(canary),
        ],
    )
    assert result.exit_code == 2
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "rollback_recommended"


def test_rollout_controller_completes_when_target_reached(tmp_path: Path) -> None:
    canary = tmp_path / "canary.json"
    state_file = tmp_path / "rollout.state.json"
    canary.write_text(json.dumps({"passed": True}), encoding="utf-8")
    state_file.write_text(
        json.dumps(
            {
                "current_phase": 100,
                "plan": [5, 25, 50, 100],
                "status": "advanced_to_100",
                "history": [],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "rollout-controller",
            "--state-file",
            str(state_file),
            "--canary-report",
            str(canary),
            "--target-phase",
            "100",
        ],
    )
    assert result.exit_code == 0
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "complete"


def test_rollout_controller_adaptive_jump_on_stability(tmp_path: Path) -> None:
    canary = tmp_path / "canary.json"
    shadow = tmp_path / "shadow.json"
    state_file = tmp_path / "rollout.state.json"
    canary.write_text(
        json.dumps({"passed": True, "deltas": {"accuracy_drop": 0.0, "reasoning_drop": 0.0}}),
        encoding="utf-8",
    )
    shadow.write_text(
        json.dumps({"summary": {"passed": True, "candidate_error_rate": 0.0, "disagreement_rate": 0.0, "latency_increase_ratio": 0.0}}),
        encoding="utf-8",
    )
    state_file.write_text(
        json.dumps(
            {
                "current_phase": 25,
                "plan": [5, 25, 50, 100],
                "status": "advanced_to_25",
                "history": [
                    {"action": "advance", "passed": True},
                    {"action": "advance", "passed": True},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "rollout-controller",
            "--state-file",
            str(state_file),
            "--canary-report",
            str(canary),
            "--shadow-report",
            str(shadow),
            "--adaptive",
            "--max-phase-increment",
            "2",
        ],
    )
    assert result.exit_code == 0
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["current_phase"] == 100


def test_rollout_controller_adaptive_hold_on_risk(tmp_path: Path) -> None:
    canary = tmp_path / "canary_risky.json"
    state_file = tmp_path / "rollout.state.json"
    canary.write_text(
        json.dumps({"passed": True, "deltas": {"accuracy_drop": 0.03, "reasoning_drop": 0.05, "cost_increase_ratio": 0.25}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "rollout-controller",
            "--state-file",
            str(state_file),
            "--canary-report",
            str(canary),
            "--adaptive",
            "--hold-risk-threshold",
            "0.5",
        ],
    )
    assert result.exit_code == 0
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["status"] == "hold"
