from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app
from fastagent.plugins.audit import sign_audit_event


runner = CliRunner()


def _event(signature_secret: str) -> dict:
    payload = {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "plugin": "sample",
        "module": "plugins.sample",
        "profile": "balanced",
        "sandbox_enabled": True,
        "timeout_seconds": 2.0,
        "memory_mb": 256,
        "duration_ms": 10.0,
        "status": "ok",
        "input_sha256": "a" * 64,
        "result_sha256": "b" * 64,
        "error": "",
    }
    payload["signature"] = sign_audit_event(payload, signature_secret)
    return payload


def test_verify_audit_pass(tmp_path: Path) -> None:
    log_file = tmp_path / "plugin_audit.jsonl"
    event = _event("secret")
    log_file.write_text(json.dumps(event) + "\n", encoding="utf-8")

    result = runner.invoke(app, ["verify-audit", "--log-file", str(log_file), "--secret", "secret"])
    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_verify_audit_fail_on_tamper(tmp_path: Path) -> None:
    log_file = tmp_path / "plugin_audit.jsonl"
    event = _event("secret")
    event["status"] = "tampered"
    log_file.write_text(json.dumps(event) + "\n", encoding="utf-8")

    result = runner.invoke(app, ["verify-audit", "--log-file", str(log_file), "--secret", "secret"])
    assert result.exit_code == 2
    assert "FAIL" in result.stdout


def test_verify_audit_allow_missing(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"
    result = runner.invoke(app, ["verify-audit", "--log-file", str(missing), "--allow-missing"])
    assert result.exit_code == 0
    assert "allowed" in result.stdout.lower()
