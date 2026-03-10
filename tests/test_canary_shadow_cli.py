from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def test_canary_shadow_simulate_pass(tmp_path: Path) -> None:
    output = tmp_path / "shadow.json"
    result = runner.invoke(
        app,
        [
            "canary-shadow",
            "--simulate",
            "--simulate-count",
            "20",
            "--simulate-degradation",
            "0.05",
            "--output-json",
            str(output),
        ],
    )
    assert result.exit_code == 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["summary"]["passed"] is True


def test_canary_shadow_simulate_fail(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "canary-shadow",
            "--simulate",
            "--simulate-count",
            "20",
            "--simulate-degradation",
            "0.9",
            "--max-disagreement-rate",
            "0.1",
        ],
    )
    assert result.exit_code == 2
    assert "FAIL" in result.stdout


def test_canary_shadow_sample_file(tmp_path: Path) -> None:
    samples = tmp_path / "samples.jsonl"
    samples.write_text(
        '{"message":"hello"}\n{"prompt":"world"}\n',
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "canary-shadow",
            "--simulate",
            "--sample-file",
            str(samples),
            "--simulate-degradation",
            "0.0",
        ],
    )
    assert result.exit_code == 0
