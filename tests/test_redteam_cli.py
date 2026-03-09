from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app

runner = CliRunner()


def test_redteam_generation(tmp_path: Path) -> None:
    output = tmp_path / "redteam.jsonl"
    result = runner.invoke(
        app,
        ["redteam", "--output", str(output), "--count", "12", "--domain", "legal agents", "--seed", "7"],
    )
    assert result.exit_code == 0
    assert output.exists()

    lines = [line for line in output.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 12

    first = json.loads(lines[0])
    assert "category" in first
    assert "prompt" in first
    assert "expected_rule" in first
