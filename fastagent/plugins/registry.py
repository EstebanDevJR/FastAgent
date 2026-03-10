from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from fastagent.plugins.manifest import upsert_plugin
from fastagent.plugins.signing import sha256_hex, verify_signature
from fastagent.plugins.trust import load_trust_policy
from fastagent.utils.project import plugin_manifest_path


DEFAULT_REGISTRY = "https://raw.githubusercontent.com/fastagent-dev/plugin-registry/main/registry.json"


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_registry(data: dict, base_dir: Path | None = None) -> dict:
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError("Registry 'plugins' field must be a list")

    normalized: list[dict] = []
    for item in plugins:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip().lower().replace("-", "_")
        if not name:
            continue
        profile = str(item.get("sandbox_profile", "balanced")).strip().lower() or "balanced"
        if profile not in {"strict", "balanced", "off"}:
            profile = "balanced"
        normalized.append(
            {
                "name": name,
                "description": str(item.get("description", "")).strip(),
                "source": str(item.get("source", "")).strip(),
                "module": str(item.get("module", f"plugins.{name}")).strip() or f"plugins.{name}",
                "filename": str(item.get("filename", f"{name}.py")).strip() or f"{name}.py",
                "sha256": str(item.get("sha256", "")).strip().lower(),
                "signing_key": str(item.get("signing_key", "")).strip(),
                "signature": str(item.get("signature", "")).strip(),
                "public_key": str(item.get("public_key", "")).strip(),
                "sandbox_profile": profile,
            }
        )

    keys = data.get("keys", [])
    normalized_keys: list[dict] = []
    if isinstance(keys, list):
        for key in keys:
            if not isinstance(key, dict):
                continue
            key_id = str(key.get("id", "")).strip()
            public_key = str(key.get("public_key", "")).strip()
            if not key_id or not public_key:
                continue
            normalized_keys.append(
                {
                    "id": key_id,
                    "algorithm": str(key.get("algorithm", "ed25519")).strip().lower() or "ed25519",
                    "public_key": public_key,
                }
            )

    return {
        "name": str(data.get("name", "fastagent-registry")).strip() or "fastagent-registry",
        "keys": normalized_keys,
        "plugins": normalized,
        "_base_dir": str(base_dir) if base_dir is not None else "",
    }


def load_registry(registry: str = DEFAULT_REGISTRY, timeout: float = 20.0) -> dict:
    location = registry.strip() or DEFAULT_REGISTRY

    if _is_http_url(location):
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required to load remote plugin registries") from exc

        response = httpx.get(location, timeout=timeout)
        if response.status_code >= 400:
            raise ValueError(f"Registry request failed ({response.status_code}) for: {location}")
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid registry JSON from {location}: {exc}") from exc
    else:
        registry_path = Path(location)
        if not registry_path.exists():
            raise FileNotFoundError(f"Registry file not found: {registry_path}")
        try:
            data = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid registry JSON in {registry_path}: {exc}") from exc
        base_dir = registry_path.resolve().parent
    if _is_http_url(location):
        base_dir = None

    if not isinstance(data, dict):
        raise ValueError("Registry must be a JSON object")
    return _normalize_registry(data, base_dir=base_dir)


def find_registry_plugin(registry_data: dict, plugin_name: str) -> dict:
    normalized = plugin_name.strip().lower().replace("-", "_")
    for item in registry_data.get("plugins", []):
        if item.get("name") == normalized:
            return item
    raise ValueError(f"Plugin '{normalized}' not found in registry")


def _find_registry_key(registry_data: dict, key_id: str) -> dict | None:
    for item in registry_data.get("keys", []):
        if item.get("id") == key_id:
            return item
    return None


def _read_source_bytes(source: str, timeout: float, base_dir: Path | None = None) -> bytes:
    if _is_http_url(source):
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("httpx is required to download remote plugins") from exc
        response = httpx.get(source, timeout=timeout)
        if response.status_code >= 400:
            raise ValueError(f"Plugin download failed ({response.status_code}) for: {source}")
        return response.content

    source_path = Path(source)
    if not source_path.is_absolute() and base_dir is not None:
        source_path = base_dir / source_path
    if not source_path.exists():
        raise FileNotFoundError(f"Plugin source file not found: {source_path}")
    return source_path.read_bytes()


def _validate_sha256(payload: bytes, expected_sha256: str) -> bool:
    digest = sha256_hex(payload)
    return digest == expected_sha256.lower()


def _is_registry_allowed(policy: dict, registry_name: str) -> bool:
    allowed = {item.strip() for item in policy.get("allowed_registries", []) if str(item).strip()}
    if not allowed:
        return True
    return registry_name in allowed


def _is_plugin_unsigned_allowed(policy: dict, plugin_name: str, allow_unsigned_flag: bool) -> bool:
    if allow_unsigned_flag:
        return True
    whitelist = {item.strip().lower() for item in policy.get("allow_unsigned_plugins", []) if str(item).strip()}
    return plugin_name.strip().lower() in whitelist


def _resolve_plugin_public_key(registry_data: dict, plugin: dict) -> tuple[str, str]:
    inline_public_key = str(plugin.get("public_key", "")).strip()
    signing_key = str(plugin.get("signing_key", "")).strip()

    if inline_public_key:
        key_id = signing_key or "inline"
        return key_id, inline_public_key

    if signing_key:
        key_record = _find_registry_key(registry_data, signing_key)
        if key_record is None:
            raise ValueError(f"Signing key '{signing_key}' not found in registry keys")
        algorithm = key_record.get("algorithm", "ed25519")
        if algorithm != "ed25519":
            raise ValueError(f"Unsupported signing algorithm '{algorithm}' for key '{signing_key}'")
        return signing_key, str(key_record.get("public_key", "")).strip()

    raise ValueError("Signed plugin is missing 'signing_key' or inline 'public_key'")


def _is_key_trusted(policy: dict, key_id: str, public_key: str) -> bool:
    trusted_ids = {item.strip() for item in policy.get("trusted_key_ids", []) if str(item).strip()}
    trusted_public_keys = {
        item.strip() for item in policy.get("trusted_public_keys", []) if str(item).strip()
    }

    if trusted_ids and key_id not in trusted_ids:
        return False
    if trusted_public_keys and public_key not in trusted_public_keys:
        return False
    return True


def install_registry_plugin(
    project_path: Path,
    registry_data: dict,
    plugin_name: str,
    enable: bool = True,
    sandbox_profile: str | None = None,
    trust_policy: Path | None = None,
    allow_unsigned: bool = False,
    overwrite: bool = False,
    timeout: float = 20.0,
) -> dict:
    policy = load_trust_policy(project_path=project_path, trust_policy=trust_policy)
    registry_name = str(registry_data.get("name", "unknown")).strip() or "unknown"
    if not _is_registry_allowed(policy, registry_name):
        raise ValueError(f"Registry '{registry_name}' is not allowed by trust policy")

    plugin = find_registry_plugin(registry_data, plugin_name)

    source = plugin.get("source", "")
    if not source:
        raise ValueError(f"Plugin '{plugin['name']}' has no source in registry")

    base_dir_raw = str(registry_data.get("_base_dir", "")).strip()
    base_dir = Path(base_dir_raw) if base_dir_raw else None
    payload = _read_source_bytes(source=source, timeout=timeout, base_dir=base_dir)
    expected_sha = str(plugin.get("sha256", "")).strip().lower()
    if expected_sha:
        if not _validate_sha256(payload, expected_sha):
            raise ValueError(f"SHA256 mismatch for plugin '{plugin['name']}'")
    elif not _is_plugin_unsigned_allowed(policy, plugin["name"], allow_unsigned):
        raise ValueError(
            f"Plugin '{plugin['name']}' is unsigned. Use --allow-unsigned to install without SHA256 verification."
        )

    signature = str(plugin.get("signature", "")).strip()
    require_signed = bool(policy.get("require_signed", True))
    if signature:
        key_id, public_key = _resolve_plugin_public_key(registry_data, plugin)
        if not _is_key_trusted(policy, key_id=key_id, public_key=public_key):
            raise ValueError(f"Signing key '{key_id}' is not trusted by policy")
        verify_signature(payload=payload, signature_b64=signature, public_key_b64=public_key)
    elif require_signed and not _is_plugin_unsigned_allowed(policy, plugin["name"], allow_unsigned):
        raise ValueError(
            f"Plugin '{plugin['name']}' is missing Ed25519 signature required by trust policy."
        )

    plugins_dir = project_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    filename = str(plugin.get("filename", f"{plugin['name']}.py")).strip() or f"{plugin['name']}.py"
    target_file = plugins_dir / filename
    if target_file.exists() and not overwrite:
        raise ValueError(f"Plugin target already exists: {target_file}. Use --overwrite to replace.")

    target_file.write_bytes(payload)

    module = str(plugin.get("module", "")).strip() or f"plugins.{Path(filename).stem}"
    profile = str(sandbox_profile or plugin.get("sandbox_profile", "balanced")).strip().lower() or "balanced"
    if profile not in {"strict", "balanced", "off"}:
        profile = "balanced"
    plugin_record = {
        "name": plugin["name"],
        "source": f"registry:{registry_name}",
        "module": module,
        "enabled": enable,
        "description": plugin.get("description", ""),
        "sandbox_profile": profile,
    }
    return upsert_plugin(plugin_manifest_path(project_path), plugin_record)
