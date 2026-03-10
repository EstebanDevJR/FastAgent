from pathlib import Path
import json

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def _init_fake_project(path: Path) -> None:
    (path / "app").mkdir(parents=True, exist_ok=True)
    (path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def test_generate_signing_key_and_sign_plugin(tmp_path: Path) -> None:
    plugin_file = tmp_path / "tool.py"
    plugin_file.write_text("def run(x: str) -> str:\n    return x\n", encoding="utf-8")

    keygen = runner.invoke(
        app,
        [
            "generate-signing-key",
            "--output-dir",
            str(tmp_path),
            "--name",
            "qa_key",
        ],
    )
    assert keygen.exit_code == 0
    private_key = tmp_path / "qa_key.private.pem"
    assert private_key.exists()

    out_json = tmp_path / "signature_bundle.json"
    signed = runner.invoke(
        app,
        [
            "sign-plugin",
            str(plugin_file),
            "--private-key",
            str(private_key),
            "--key-id",
            "qa-key-1",
            "--include-key",
            "--output",
            str(out_json),
        ],
    )
    assert signed.exit_code == 0
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert "plugin" in data
    assert "signature" in data["plugin"]
    assert data["plugin"]["sandbox_profile"] == "balanced"
    assert "key" in data


def test_init_trust_creates_policy_file(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "init-trust",
            "--project-path",
            str(tmp_path),
            "--allowed-registry",
            "qa-registry",
            "--trusted-key-id",
            "qa-key-1",
        ],
    )
    assert result.exit_code == 0
    policy = tmp_path / "fastagent.trust.json"
    assert policy.exists()
    data = json.loads(policy.read_text(encoding="utf-8"))
    assert data["require_signed"] is True
    assert "qa-registry" in data["allowed_registries"]
    assert "qa-key-1" in data["trusted_key_ids"]
