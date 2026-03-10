from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def _init_fake_project(path: Path) -> None:
    (path / "app").mkdir(parents=True, exist_ok=True)
    (path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def test_init_ci_creates_expected_files(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)
    result = runner.invoke(app, ["init-ci", "--project-path", str(tmp_path)])

    assert result.exit_code == 0
    assert "CI files ready" in result.stdout

    workflow = tmp_path / ".github" / "workflows" / "fastagent-eval-gate.yml"
    config = tmp_path / "fastagent.eval.json"
    dataset = tmp_path / "examples" / "eval_dataset.sample.jsonl"
    shadow_dataset = tmp_path / "examples" / "shadow_samples.sample.jsonl"

    assert workflow.exists()
    assert config.exists()
    assert dataset.exists()
    assert shadow_dataset.exists()
    workflow_text = workflow.read_text(encoding="utf-8")
    assert "verify-audit" in workflow_text
    assert "canary-check" in workflow_text
    assert "canary-shadow" in workflow_text
    assert "rollback-webhook" in workflow_text
    assert "rollout-controller" in workflow_text
    assert "--adaptive" in workflow_text
    assert "rollout-apply" in workflow_text

    config_data = json.loads(config.read_text(encoding="utf-8"))
    assert "thresholds" in config_data
    assert config_data["dataset"] == "examples/eval_dataset.sample.jsonl"


def test_init_ci_no_overwrite(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)
    config = tmp_path / "fastagent.eval.json"
    config.write_text('{"dataset":"custom.jsonl"}\n', encoding="utf-8")

    result = runner.invoke(app, ["init-ci", "--project-path", str(tmp_path)])

    assert result.exit_code == 0
    assert "skipped (already exists)" in result.stdout
    assert json.loads(config.read_text(encoding="utf-8"))["dataset"] == "custom.jsonl"
