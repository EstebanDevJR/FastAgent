from pathlib import Path
import hashlib
import json

import pytest

from fastagent.plugins.registry import find_registry_plugin, install_registry_plugin, load_registry


def test_load_registry_from_file_and_find(tmp_path: Path) -> None:
    source_file = tmp_path / "sample_plugin.py"
    source_file.write_text("def tool(x: str) -> str:\n    return x\n", encoding="utf-8")
    sha = hashlib.sha256(source_file.read_bytes()).hexdigest()

    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "name": "local-test-registry",
                "plugins": [
                    {
                        "name": "sample_plugin",
                        "source": str(source_file),
                        "module": "plugins.sample_plugin",
                        "filename": "sample_plugin.py",
                        "sha256": sha,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    data = load_registry(str(registry_path))
    plugin = find_registry_plugin(data, "sample-plugin")
    assert plugin["name"] == "sample_plugin"
    assert plugin["sha256"] == sha
    assert plugin["sandbox_profile"] == "balanced"


def test_install_registry_plugin_requires_signature_by_default(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "app").mkdir(parents=True, exist_ok=True)
    (project / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (project / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    source_file = tmp_path / "unsigned_plugin.py"
    source_file.write_text("def run(x: str) -> str:\n    return x\n", encoding="utf-8")

    registry = {
        "name": "unsigned-registry",
        "plugins": [
            {
                "name": "unsigned_plugin",
                "source": str(source_file),
                "module": "plugins.unsigned_plugin",
                "filename": "unsigned_plugin.py",
                "sha256": "",
            }
        ],
    }

    with pytest.raises(ValueError, match="unsigned"):
        install_registry_plugin(project_path=project, registry_data=registry, plugin_name="unsigned_plugin")


def test_install_registry_plugin_sha_mismatch(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "app").mkdir(parents=True, exist_ok=True)
    (project / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (project / "requirements.txt").write_text("fastapi\n", encoding="utf-8")

    source_file = tmp_path / "bad_plugin.py"
    source_file.write_text("def run(x: str) -> str:\n    return x\n", encoding="utf-8")

    registry = {
        "name": "mismatch-registry",
        "plugins": [
            {
                "name": "bad_plugin",
                "source": str(source_file),
                "module": "plugins.bad_plugin",
                "filename": "bad_plugin.py",
                "sha256": "0" * 64,
            }
        ],
    }

    with pytest.raises(ValueError, match="SHA256 mismatch"):
        install_registry_plugin(project_path=project, registry_data=registry, plugin_name="bad_plugin")
