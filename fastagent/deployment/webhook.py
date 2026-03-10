from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json


def build_rollback_payload(
    deployment_id: str,
    reason: str,
    source: str = "fastagent-cli",
    metadata: dict | None = None,
    canary_report: dict | None = None,
) -> dict:
    return {
        "event": "rollback_requested",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "deployment_id": deployment_id,
        "reason": reason,
        "source": source,
        "metadata": metadata or {},
        "canary_report": canary_report or {},
    }


def build_deployment_payload(
    event: str,
    deployment_id: str,
    reason: str,
    source: str = "fastagent-cli",
    environment: str = "",
    metadata: dict | None = None,
    canary_report: dict | None = None,
    shadow_report: dict | None = None,
    rollout_decision: dict | None = None,
    rollout_state: dict | None = None,
) -> dict:
    return {
        "event": event.strip() or "deployment_event",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "deployment_id": deployment_id,
        "reason": reason,
        "source": source,
        "environment": environment.strip(),
        "metadata": metadata or {},
        "canary_report": canary_report or {},
        "shadow_report": shadow_report or {},
        "rollout_decision": rollout_decision or {},
        "rollout_state": rollout_state or {},
    }


def sign_payload(payload: dict, secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def post_signed_webhook(
    url: str,
    payload: dict,
    secret: str,
    timeout: float = 15.0,
    event_header: str | None = None,
) -> tuple[int, str]:
    if not url.strip():
        raise ValueError("Webhook URL is required")
    if not secret.strip():
        raise ValueError("Webhook secret is required")

    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required to call webhook") from exc

    signature = sign_payload(payload, secret=secret)
    event_name = event_header or str(payload.get("event", "deployment_event"))
    headers = {
        "Content-Type": "application/json",
        "X-FastAgent-Event": event_name,
        "X-FastAgent-Signature": signature,
    }
    response = httpx.post(url, json=payload, headers=headers, timeout=max(0.1, timeout))
    text = response.text.strip() if isinstance(response.text, str) else ""
    return response.status_code, text


def post_rollback_webhook(
    url: str,
    payload: dict,
    secret: str,
    timeout: float = 15.0,
) -> tuple[int, str]:
    return post_signed_webhook(
        url=url,
        payload=payload,
        secret=secret,
        timeout=timeout,
        event_header="rollback_requested",
    )
