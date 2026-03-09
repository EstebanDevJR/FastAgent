from pathlib import Path

from fastagent.plugins.manifest import load_manifest, remove_plugin, set_plugin_enabled, upsert_plugin


def test_manifest_upsert_enable_disable_remove(tmp_path: Path) -> None:
    manifest_path = tmp_path / "fastagent.plugins.json"

    upsert_plugin(
        manifest_path,
        {
            "name": "sample_plugin",
            "source": "local",
            "module": "plugins.sample_plugin",
            "enabled": True,
            "description": "sample",
        },
    )
    data = load_manifest(manifest_path)
    assert len(data["plugins"]) == 1
    assert data["plugins"][0]["enabled"] is True

    set_plugin_enabled(manifest_path, "sample_plugin", False)
    data = load_manifest(manifest_path)
    assert data["plugins"][0]["enabled"] is False

    remove_plugin(manifest_path, "sample_plugin")
    data = load_manifest(manifest_path)
    assert data["plugins"] == []
