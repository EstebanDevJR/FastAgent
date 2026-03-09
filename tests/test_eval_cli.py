from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def test_eval_accepts_comment_lines(tmp_path: Path) -> None:
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        "# sample\n"
        "{\"expected\":\"hello\",\"predicted\":\"hello world\"}\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["eval", "--dataset", str(dataset)])

    assert result.exit_code == 0
    assert "FastAgent Evaluation" in result.stdout


def test_eval_reports_invalid_json_line(tmp_path: Path) -> None:
    dataset = tmp_path / "eval_bad.jsonl"
    dataset.write_text("{bad json}\n", encoding="utf-8")

    result = runner.invoke(app, ["eval", "--dataset", str(dataset)])

    assert result.exit_code != 0
    assert "Invalid JSON on line 1" in result.stdout


def test_eval_gate_pass_and_report(tmp_path: Path) -> None:
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        "{\"expected\":\"hello\",\"predicted\":\"hello world\"}\n",
        encoding="utf-8",
    )
    config = tmp_path / "eval_config.json"
    config.write_text(
        json.dumps(
            {
                "dataset": str(dataset),
                "thresholds": {
                    "accuracy_min": 0.9,
                    "reasoning_quality_min": 0.9,
                    "tool_usage_min": 0.0,
                    "hallucinations_max": 0.2,
                    "cost_max": 1.0,
                },
                "report_path": str(tmp_path / "report.json"),
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["eval", "--config", str(config), "--gate"])

    assert result.exit_code == 0
    assert "FastAgent Eval Gate" in result.stdout
    assert (tmp_path / "report.json").exists()


def test_eval_gate_fail_exit_code(tmp_path: Path) -> None:
    dataset = tmp_path / "eval_fail.jsonl"
    dataset.write_text(
        "{\"expected\":\"hello\",\"predicted\":\"unrelated\"}\n",
        encoding="utf-8",
    )
    config = tmp_path / "eval_config_fail.json"
    config.write_text(
        json.dumps(
            {
                "dataset": str(dataset),
                "thresholds": {"accuracy_min": 1.0},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["eval", "--config", str(config), "--gate"])

    assert result.exit_code == 2
    assert "FAIL" in result.stdout
