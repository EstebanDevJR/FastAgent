from pathlib import Path
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from typer.testing import CliRunner

from fastagent.cli.main import app
from fastagent.plugins.manifest import load_manifest
from fastagent.plugins.signing import public_key_to_base64, sha256_hex, sign_payload


runner = CliRunner()


def _init_fake_project(path: Path) -> None:
    (path / "app").mkdir(parents=True, exist_ok=True)
    (path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def _signed_registry_entry(plugin_source: Path, plugin_name: str, key_id: str = "qa-signing-key") -> dict:
    payload = plugin_source.read_bytes()
    private_key = Ed25519PrivateKey.generate()
    signature = sign_payload(payload, private_key)
    public_key = public_key_to_base64(private_key.public_key())

    return {
        "keys": [{"id": key_id, "algorithm": "ed25519", "public_key": public_key}],
        "plugin": {
            "name": plugin_name,
            "source": str(plugin_source),
            "module": f"plugins.{plugin_name}",
            "filename": f"{plugin_name}.py",
            "sha256": sha256_hex(payload),
            "signing_key": key_id,
            "signature": signature,
        },
    }


def test_install_plugin_from_local_registry(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)

    plugin_source = tmp_path / "currency_tool.py"
    plugin_source.write_text("def convert(amount: str) -> str:\n    return amount\n", encoding="utf-8")
    signed = _signed_registry_entry(plugin_source=plugin_source, plugin_name="currency_tool")

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "name": "qa-registry",
                "keys": signed["keys"],
                "plugins": [
                    {
                        "description": "Currency conversion plugin.",
                        **signed["plugin"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "install-plugin",
            "currency_tool",
            "--project-path",
            str(tmp_path),
            "--registry",
            str(registry_path),
            "--sandbox-profile",
            "strict",
        ],
    )
    assert result.exit_code == 0
    assert "Plugin Installed" in result.stdout
    assert (tmp_path / "plugins" / "currency_tool.py").exists()

    manifest = load_manifest(tmp_path / "fastagent.plugins.json")
    assert len(manifest["plugins"]) == 1
    assert manifest["plugins"][0]["name"] == "currency_tool"
    assert manifest["plugins"][0]["source"] == "registry:qa-registry"
    assert manifest["plugins"][0]["sandbox_profile"] == "strict"


def test_install_plugin_unsigned_requires_flag(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)

    plugin_source = tmp_path / "unsigned.py"
    plugin_source.write_text("def run(x: str) -> str:\n    return x\n", encoding="utf-8")

    registry_path = tmp_path / "registry_unsigned.json"
    registry_path.write_text(
        json.dumps(
            {
                "name": "unsigned-registry",
                "plugins": [
                    {
                        "name": "unsigned",
                        "source": str(plugin_source),
                        "filename": "unsigned.py",
                        "module": "plugins.unsigned",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    fail_result = runner.invoke(
        app,
        [
            "install-plugin",
            "unsigned",
            "--project-path",
            str(tmp_path),
            "--registry",
            str(registry_path),
        ],
    )
    assert fail_result.exit_code != 0
    assert "unsigned" in fail_result.stdout.lower()

    ok_result = runner.invoke(
        app,
        [
            "install-plugin",
            "unsigned",
            "--project-path",
            str(tmp_path),
            "--registry",
            str(registry_path),
            "--allow-unsigned",
        ],
    )
    assert ok_result.exit_code == 0
    assert (tmp_path / "plugins" / "unsigned.py").exists()


def test_install_plugin_registry_relative_source_path(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)

    registry_root = tmp_path / "registry_root"
    (registry_root / "plugins").mkdir(parents=True, exist_ok=True)
    plugin_source = registry_root / "plugins" / "relative_tool.py"
    plugin_source.write_text("def run(x: str) -> str:\n    return x\n", encoding="utf-8")
    signed = _signed_registry_entry(plugin_source=plugin_source, plugin_name="relative_tool")

    registry_path = registry_root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "name": "relative-registry",
                "keys": signed["keys"],
                "plugins": [
                    {
                        "name": "relative_tool",
                        "source": "plugins/relative_tool.py",
                        "filename": "relative_tool.py",
                        "module": "plugins.relative_tool",
                        "sha256": signed["plugin"]["sha256"],
                        "signing_key": signed["plugin"]["signing_key"],
                        "signature": signed["plugin"]["signature"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "install-plugin",
            "relative_tool",
            "--project-path",
            str(tmp_path),
            "--registry",
            str(registry_path),
        ],
    )

    assert result.exit_code == 0
    assert (tmp_path / "plugins" / "relative_tool.py").exists()
