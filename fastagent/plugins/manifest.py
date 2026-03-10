from pathlib import Path
import json


DEFAULT_MANIFEST = {"plugins": []}
SANDBOX_PROFILE_OPTIONS = {"strict", "balanced", "off"}


def _normalize_plugin_record(plugin: dict) -> dict | None:
    if not isinstance(plugin, dict):
        return None

    name = str(plugin.get("name", "")).strip()
    if not name:
        return None

    sandbox_profile = str(plugin.get("sandbox_profile", "balanced")).strip().lower() or "balanced"
    if sandbox_profile not in SANDBOX_PROFILE_OPTIONS:
        sandbox_profile = "balanced"

    return {
        "name": name,
        "source": str(plugin.get("source", "local")).strip() or "local",
        "module": str(plugin.get("module", f"plugins.{name}")).strip() or f"plugins.{name}",
        "enabled": bool(plugin.get("enabled", True)),
        "description": str(plugin.get("description", "")).strip(),
        "sandbox_profile": sandbox_profile,
    }


def load_manifest(path: Path) -> dict:
    if not path.exists():
        return {"plugins": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid plugin manifest JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("Plugin manifest must be a JSON object")

    plugins = data.get("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError("Plugin manifest field 'plugins' must be a list")

    normalized = []
    for plugin in plugins:
        normalized_plugin = _normalize_plugin_record(plugin)
        if normalized_plugin is not None:
            normalized.append(normalized_plugin)

    return {"plugins": normalized}


def save_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def upsert_plugin(path: Path, plugin: dict) -> dict:
    manifest = load_manifest(path)
    plugins = manifest["plugins"]
    normalized_input = _normalize_plugin_record(plugin)
    if normalized_input is None:
        raise ValueError("Plugin record is missing required field 'name'")

    replaced = False
    for idx, item in enumerate(plugins):
        if item.get("name") == normalized_input["name"]:
            plugins[idx] = normalized_input
            replaced = True
            break

    if not replaced:
        plugins.append(normalized_input)

    save_manifest(path, manifest)
    return manifest


def remove_plugin(path: Path, plugin_name: str) -> dict:
    manifest = load_manifest(path)
    manifest["plugins"] = [item for item in manifest["plugins"] if item.get("name") != plugin_name]
    save_manifest(path, manifest)
    return manifest


def set_plugin_enabled(path: Path, plugin_name: str, enabled: bool) -> dict:
    manifest = load_manifest(path)
    found = False
    for item in manifest["plugins"]:
        if item.get("name") == plugin_name:
            item["enabled"] = enabled
            found = True
            break
    if not found:
        raise ValueError(f"Plugin '{plugin_name}' not found")
    save_manifest(path, manifest)
    return manifest
