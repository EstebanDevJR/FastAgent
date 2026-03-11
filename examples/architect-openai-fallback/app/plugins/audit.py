from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path


def _canonical_payload(event: dict) -> bytes:
    payload = dict(event)
    payload.pop("signature", None)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _sign_event(event: dict, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), _canonical_payload(event), hashlib.sha256).hexdigest()
    return digest


def write_plugin_audit_event(
    *,
    plugin_name: str,
    module: str,
    profile: str,
    sandbox_enabled: bool,
    timeout_seconds: float,
    memory_mb: int,
    duration_ms: float,
    status: str,
    input_text: str,
    result: str,
    error: str,
    log_path: str,
    secret: str,
    enabled: bool = True,
) -> dict:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "plugin": plugin_name,
        "module": module,
        "profile": profile,
        "sandbox_enabled": sandbox_enabled,
        "timeout_seconds": timeout_seconds,
        "memory_mb": memory_mb,
        "duration_ms": round(duration_ms, 3),
        "status": status,
        "input_sha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
        "result_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest() if result else "",
        "error": error,
    }
    event["signature"] = _sign_event(event, secret or "fastagent-dev-audit-secret")

    if enabled:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    return event


def verify_plugin_audit_signature(event: dict, secret: str) -> bool:
    signature = str(event.get("signature", "")).strip()
    if not signature:
        return False
    expected = _sign_event(event, secret or "fastagent-dev-audit-secret")
    return hmac.compare_digest(signature, expected)
