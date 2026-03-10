from pathlib import Path
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fastagent.plugins.registry import install_registry_plugin
from fastagent.plugins.signing import public_key_to_base64, sha256_hex, sign_payload


def _init_fake_project(path: Path) -> None:
    (path / "app").mkdir(parents=True, exist_ok=True)
    (path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def test_install_registry_plugin_respects_trusted_key_id(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _init_fake_project(project)

    plugin_source = tmp_path / "secure_tool.py"
    plugin_source.write_text("def run(x: str) -> str:\n    return x\n", encoding="utf-8")
    payload = plugin_source.read_bytes()

    private_key = Ed25519PrivateKey.generate()
    public_key = public_key_to_base64(private_key.public_key())
    signature = sign_payload(payload, private_key)

    registry = {
        "name": "trusted-registry",
        "keys": [{"id": "key-1", "algorithm": "ed25519", "public_key": public_key}],
        "plugins": [
            {
                "name": "secure_tool",
                "source": str(plugin_source),
                "module": "plugins.secure_tool",
                "filename": "secure_tool.py",
                "sha256": sha256_hex(payload),
                "signing_key": "key-1",
                "signature": signature,
            }
        ],
    }

    trust_policy = project / "fastagent.trust.json"
    trust_policy.write_text(
        json.dumps(
            {
                "require_signed": True,
                "trusted_key_ids": ["key-1"],
                "allowed_registries": ["trusted-registry"],
            }
        ),
        encoding="utf-8",
    )

    manifest = install_registry_plugin(
        project_path=project,
        registry_data=registry,
        plugin_name="secure_tool",
    )
    assert len(manifest["plugins"]) == 1
    assert (project / "plugins" / "secure_tool.py").exists()


def test_install_registry_plugin_rejects_untrusted_key(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _init_fake_project(project)

    plugin_source = tmp_path / "tool.py"
    plugin_source.write_text("def run(x: str) -> str:\n    return x\n", encoding="utf-8")
    payload = plugin_source.read_bytes()

    private_key = Ed25519PrivateKey.generate()
    public_key = public_key_to_base64(private_key.public_key())
    signature = sign_payload(payload, private_key)

    registry = {
        "name": "trusted-registry",
        "keys": [{"id": "real-key", "algorithm": "ed25519", "public_key": public_key}],
        "plugins": [
            {
                "name": "tool",
                "source": str(plugin_source),
                "module": "plugins.tool",
                "filename": "tool.py",
                "sha256": sha256_hex(payload),
                "signing_key": "real-key",
                "signature": signature,
            }
        ],
    }

    (project / "fastagent.trust.json").write_text(
        json.dumps(
            {
                "require_signed": True,
                "trusted_key_ids": ["other-key"],
                "allowed_registries": ["trusted-registry"],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not trusted"):
        install_registry_plugin(project_path=project, registry_data=registry, plugin_name="tool")
