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


def test_eval_judge_reproducible_seed(tmp_path: Path) -> None:
    dataset = tmp_path / "eval_judge.jsonl"
    dataset.write_text(
        "{\"expected\":\"contract risk\",\"predicted\":\"contract risk is medium source:policy\"}\n",
        encoding="utf-8",
    )
    report_a = tmp_path / "judge_a.json"
    report_b = tmp_path / "judge_b.json"

    result_a = runner.invoke(
        app,
        ["eval", "--dataset", str(dataset), "--judge", "--judge-seed", "7", "--output-json", str(report_a)],
    )
    result_b = runner.invoke(
        app,
        ["eval", "--dataset", str(dataset), "--judge", "--judge-seed", "7", "--output-json", str(report_b)],
    )

    assert result_a.exit_code == 0
    assert result_b.exit_code == 0
    judge_a = json.loads(report_a.read_text(encoding="utf-8"))["judge"]
    judge_b = json.loads(report_b.read_text(encoding="utf-8"))["judge"]
    assert judge_a["overall_score"] == judge_b["overall_score"]
    assert judge_a["criteria_scores"] == judge_b["criteria_scores"]


def test_eval_gate_with_judge_threshold(tmp_path: Path) -> None:
    dataset = tmp_path / "eval_judge_gate.jsonl"
    dataset.write_text(
        "{\"expected\":\"hello\",\"predicted\":\"irrelevant\"}\n",
        encoding="utf-8",
    )
    config = tmp_path / "eval_judge_gate.json"
    config.write_text(
        json.dumps(
            {
                "dataset": str(dataset),
                "judge": {"enabled": True, "seed": 11},
                "thresholds": {"judge_score_min": 0.9},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["eval", "--config", str(config), "--gate"])

    assert result.exit_code == 2
    assert "judge_score" in result.stdout
