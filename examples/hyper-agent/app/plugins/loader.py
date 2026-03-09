from pathlib import Path
import json


def _manifest_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fastagent.plugins.json"


def load_plugins() -> list[dict]:
    manifest = _manifest_path()
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list):
        return []
    return [item for item in plugins if isinstance(item, dict)]


def enabled_plugins() -> list[dict]:
    return [plugin for plugin in load_plugins() if bool(plugin.get("enabled", True))]
