from __future__ import annotations

import json
from pathlib import Path


DEFAULT_TRUST_POLICY = {
    "require_signed": True,
    "trusted_key_ids": [],
    "trusted_public_keys": [],
    "allowed_registries": [],
    "allow_unsigned_plugins": [],
}


def _normalize_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen = set()
    for item in values:
        text = str(item).strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def normalize_trust_policy(data: dict) -> dict:
    return {
        "require_signed": bool(data.get("require_signed", True)),
        "trusted_key_ids": _normalize_list(data.get("trusted_key_ids", [])),
        "trusted_public_keys": _normalize_list(data.get("trusted_public_keys", [])),
        "allowed_registries": _normalize_list(data.get("allowed_registries", [])),
        "allow_unsigned_plugins": _normalize_list(data.get("allow_unsigned_plugins", [])),
    }


def load_trust_policy(project_path: Path, trust_policy: Path | None = None) -> dict:
    policy_path = trust_policy or (project_path / "fastagent.trust.json")
    if not policy_path.exists():
        return dict(DEFAULT_TRUST_POLICY)
    try:
        raw = json.loads(policy_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid trust policy JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Trust policy must be a JSON object")
    return normalize_trust_policy(raw)


def save_trust_policy(policy_path: Path, policy: dict) -> None:
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(normalize_trust_policy(policy), indent=2) + "\n", encoding="utf-8")
