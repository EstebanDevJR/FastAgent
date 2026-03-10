from __future__ import annotations

from datetime import datetime, timezone


CHANNEL_OPTIONS = {"auto", "slack", "teams", "generic"}


def detect_channel(url: str, channel: str = "auto") -> str:
    normalized = channel.strip().lower() or "auto"
    if normalized in {"slack", "teams", "generic"}:
        return normalized
    lower_url = url.strip().lower()
    if "hooks.slack.com" in lower_url:
        return "slack"
    if "office.com/webhook" in lower_url or "outlook.office.com/webhook" in lower_url or "logic.azure.com" in lower_url:
        return "teams"
    return "generic"


def build_escalation_payload(
    channel: str,
    deployment_id: str,
    environment: str,
    request: dict,
    state_file: str,
) -> dict:
    request_id = str(request.get("id", ""))
    reason = str(request.get("reason", "approval_pending"))
    expires_at = str(request.get("expires_at", ""))
    current_phase = request.get("current_phase", "")
    next_phase = request.get("next_phase", "")
    message = (
        f"FastAgent approval escalation: request={request_id} deployment={deployment_id} "
        f"env={environment} reason={reason} phase={current_phase}->{next_phase} expires_at={expires_at}"
    )

    if channel == "slack":
        return {"text": message}
    if channel == "teams":
        return {"text": message}
    return {
        "event": "approval_escalation",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": message,
        "deployment_id": deployment_id,
        "environment": environment,
        "request_id": request_id,
        "state_file": state_file,
        "request": request,
    }


def post_escalation_notification(
    url: str,
    payload: dict,
    timeout: float = 15.0,
    secret: str = "",
) -> tuple[int, str]:
    if not url.strip():
        raise ValueError("Escalation webhook URL is required")
    if timeout <= 0:
        raise ValueError("Escalation webhook timeout must be > 0")

    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required to call escalation webhook") from exc

    headers = {"Content-Type": "application/json"}
    if secret.strip():
        from fastagent.deployment.webhook import sign_payload

        headers["X-FastAgent-Signature"] = sign_payload(payload, secret.strip())

    response = httpx.post(url.strip(), json=payload, headers=headers, timeout=max(0.1, timeout))
    text = response.text.strip() if isinstance(response.text, str) else ""
    return response.status_code, text
