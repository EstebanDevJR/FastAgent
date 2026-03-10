from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def test_canary_check_pass(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        json.dumps({"metrics": {"accuracy": 0.9, "reasoning_quality": 0.9, "hallucinations": 0.1, "cost": 1.0}}),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps({"metrics": {"accuracy": 0.89, "reasoning_quality": 0.88, "hallucinations": 0.12, "cost": 1.1}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["canary-check", "--baseline-report", str(baseline), "--candidate-report", str(candidate)],
    )
    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_canary_check_fail_and_rollback(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    baseline.write_text(
        json.dumps({"metrics": {"accuracy": 0.9, "reasoning_quality": 0.9, "hallucinations": 0.1, "cost": 1.0}}),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps({"metrics": {"accuracy": 0.7, "reasoning_quality": 0.6, "hallucinations": 0.5, "cost": 2.0}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["canary-check", "--baseline-report", str(baseline), "--candidate-report", str(candidate)],
    )
    assert result.exit_code == 2
    assert "rollback_recommended" in result.stdout
