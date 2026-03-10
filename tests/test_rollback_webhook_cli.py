from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def test_rollback_webhook_dry_run(tmp_path: Path) -> None:
    canary_report = tmp_path / "canary.json"
    canary_report.write_text(json.dumps({"passed": False, "rollback_recommended": True}), encoding="utf-8")
    output = tmp_path / "rollback.json"

    result = runner.invoke(
        app,
        [
            "rollback-webhook",
            "--url",
            "https://example.com/rollback",
            "--secret",
            "test-secret",
            "--deployment-id",
            "deploy-123",
            "--canary-report",
            str(canary_report),
            "--dry-run",
            "--output-json",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["payload"]["deployment_id"] == "deploy-123"
    assert payload["signature"]


def test_rollback_webhook_requires_url_and_secret(tmp_path: Path) -> None:
    result = runner.invoke(app, ["rollback-webhook", "--dry-run"])
    assert result.exit_code != 0
    assert "url is required" in result.stdout.lower()
