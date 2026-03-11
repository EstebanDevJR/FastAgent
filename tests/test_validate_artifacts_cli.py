from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def test_validate_artifacts_pass(tmp_path: Path) -> None:
    eval_report = tmp_path / "eval_report.json"
    eval_report.write_text(
        json.dumps(
            {
                "dataset": "x.jsonl",
                "metrics": {
                    "accuracy": 0.9,
                    "reasoning_quality": 0.9,
                    "tool_usage": 0.8,
                    "hallucinations": 0.1,
                    "cost": 1.2,
                },
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "validation.json"
    result = runner.invoke(
        app,
        [
            "validate-artifacts",
            "--artifact",
            f"eval_report:{eval_report}",
            "--output-json",
            str(output),
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True


def test_validate_artifacts_fail_for_missing_fields(tmp_path: Path) -> None:
    canary = tmp_path / "canary.json"
    canary.write_text(json.dumps({"passed": True}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "validate-artifacts",
            "--artifact",
            f"canary_report:{canary}",
        ],
    )
    assert result.exit_code == 2
