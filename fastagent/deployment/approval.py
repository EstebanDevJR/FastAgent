from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path


def load_approval_state(path: Path) -> dict:
    if not path.exists():
        return {"requests": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid approval state JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Approval state must be a JSON object")
    requests = payload.get("requests", [])
    if not isinstance(requests, list):
        requests = []
    payload["requests"] = [item for item in requests if isinstance(item, dict)]
    return payload


def save_approval_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def find_request(state: dict, request_id: str) -> dict | None:
    for item in _requests(state):
        if str(item.get("id", "")).strip() == request_id.strip():
            return item
    return None


def get_or_create_pending_request(
    state: dict,
    deployment_id: str,
    environment: str,
    reason: str,
    decision: dict,
    apply_report: dict,
    canary_payload: dict,
    shadow_payload: dict | None,
    ttl_minutes: int = 60,
) -> dict:
    current_phase = int(decision.get("current_phase", 0))
    next_phase = int(decision.get("next_phase", current_phase))
    for item in _requests(state):
        if (
            item.get("status") == "pending"
            and item.get("deployment_id") == deployment_id
            and item.get("environment") == environment
            and item.get("reason") == reason
            and int(item.get("current_phase", -1)) == current_phase
            and int(item.get("next_phase", -1)) == next_phase
        ):
            ensure_request_expiry(item, ttl_minutes=ttl_minutes)
            return item

    request_id = _new_request_id(state)
    now = _now_iso()
    ttl = max(1, int(ttl_minutes))
    expires = _format_iso(_parse_iso(now) + timedelta(minutes=ttl))
    request = {
        "id": request_id,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "deployment_id": deployment_id,
        "environment": environment,
        "reason": reason,
        "current_phase": current_phase,
        "next_phase": next_phase,
        "risk_score": float(decision.get("risk_score", 0.0)),
        "decision": decision,
        "apply": {
            "enabled": bool(apply_report.get("enabled", False)),
            "executed": bool(apply_report.get("executed", False)),
            "status_code": int(apply_report.get("status_code", 0)),
        },
        "canary_passed": bool(canary_payload.get("passed", False)),
        "shadow_passed": _shadow_passed(shadow_payload),
        "ttl_minutes": ttl,
        "expires_at": expires,
        "expired_at": "",
        "escalation_count": 0,
        "last_escalated_at": "",
        "last_escalation": {},
        "approver": "",
        "notes": "",
    }
    _requests(state).append(request)
    return request


def resolve_request(
    state: dict,
    request_id: str,
    decision: str,
    approver: str,
    notes: str = "",
) -> dict:
    request = find_request(state, request_id)
    if request is None:
        raise ValueError(f"Approval request not found: {request_id}")
    if request.get("status") != "pending":
        raise ValueError(f"Approval request is already resolved: {request_id}")

    normalized = decision.strip().lower()
    if normalized not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")

    request["status"] = "approved" if normalized == "approve" else "rejected"
    request["approver"] = approver.strip() or "unknown"
    request["notes"] = notes.strip()
    request["updated_at"] = _now_iso()
    return request


def ensure_request_expiry(request: dict, ttl_minutes: int = 60) -> dict:
    ttl = max(1, int(ttl_minutes))
    request["ttl_minutes"] = ttl
    created_at = _parse_iso(str(request.get("created_at", ""))) or datetime.now(timezone.utc)
    expires_at = _parse_iso(str(request.get("expires_at", "")))
    if expires_at is None:
        expires_at = created_at + timedelta(minutes=ttl)
        request["expires_at"] = _format_iso(expires_at)
    return request


def is_request_expired(request: dict, now: datetime | None = None) -> bool:
    now_dt = now or datetime.now(timezone.utc)
    expires = _parse_iso(str(request.get("expires_at", "")))
    if expires is None:
        return False
    return now_dt >= expires


def mark_request_expired(request: dict, notes: str = "") -> dict:
    if str(request.get("status", "")).strip() == "pending":
        request["status"] = "expired"
        if notes.strip():
            request["notes"] = notes.strip()
        request["expired_at"] = _now_iso()
        request["updated_at"] = _now_iso()
    return request


def should_escalate_request(request: dict, cooldown_minutes: int = 60) -> bool:
    status = str(request.get("status", "")).strip()
    if status not in {"pending", "expired"}:
        return False
    cooldown = max(1, int(cooldown_minutes))
    last = _parse_iso(str(request.get("last_escalated_at", "")))
    if last is None:
        return True
    return datetime.now(timezone.utc) >= (last + timedelta(minutes=cooldown))


def record_request_escalation(
    request: dict,
    channel: str,
    url: str,
    dry_run: bool,
    attempted: bool,
    sent: bool,
    status_code: int,
    error: str = "",
    response: str = "",
    incident_key: str = "",
    target_key: str = "",
) -> dict:
    count = int(request.get("escalation_count", 0))
    request["escalation_count"] = count + 1
    now = _now_iso()
    request["last_escalated_at"] = now
    request["last_escalation"] = {
        "timestamp": now,
        "channel": channel,
        "url": url,
        "dry_run": dry_run,
        "attempted": attempted,
        "sent": sent,
        "status_code": int(status_code),
        "error": error,
        "response": response,
        "incident_key": incident_key,
        "target_key": target_key,
    }
    _upsert_escalation_target(
        request=request,
        target_key=target_key or _default_target_key(channel=channel, url=url),
        incident_key=incident_key,
        channel=channel,
        url=url,
        dry_run=dry_run,
        attempted=attempted,
        sent=sent,
        status_code=int(status_code),
        error=error,
        response=response,
        timestamp=now,
    )
    request["updated_at"] = now
    return request


def build_request_incident_key(request: dict) -> str:
    return "|".join(
        [
            str(request.get("id", "")),
            str(request.get("status", "")),
            str(request.get("reason", "")),
            str(request.get("current_phase", "")),
            str(request.get("next_phase", "")),
            str(request.get("expires_at", "")),
        ]
    )


def is_target_deduped(request: dict, target_key: str, incident_key: str) -> bool:
    targets = request.get("escalation_targets", {})
    if not isinstance(targets, dict):
        return False
    target = targets.get(target_key, {})
    if not isinstance(target, dict):
        return False
    if str(target.get("incident_key", "")) != incident_key:
        return False
    status_code = int(target.get("status_code", 0))
    return status_code < 400


def _requests(state: dict) -> list[dict]:
    requests = state.get("requests")
    if not isinstance(requests, list):
        state["requests"] = []
        return state["requests"]
    return requests


def _new_request_id(state: dict) -> str:
    prefix = datetime.now(timezone.utc).strftime("apr-%Y%m%d-%H%M%S")
    existing = {str(item.get("id", "")) for item in _requests(state)}
    idx = 1
    while True:
        candidate = f"{prefix}-{idx:03d}"
        if candidate not in existing:
            return candidate
        idx += 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_iso(value: datetime) -> str:
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _upsert_escalation_target(
    request: dict,
    target_key: str,
    incident_key: str,
    channel: str,
    url: str,
    dry_run: bool,
    attempted: bool,
    sent: bool,
    status_code: int,
    error: str,
    response: str,
    timestamp: str,
) -> None:
    targets = request.get("escalation_targets")
    if not isinstance(targets, dict):
        targets = {}
        request["escalation_targets"] = targets
    targets[target_key] = {
        "timestamp": timestamp,
        "incident_key": incident_key,
        "channel": channel,
        "url": url,
        "dry_run": dry_run,
        "attempted": attempted,
        "sent": sent,
        "status_code": int(status_code),
        "error": error,
        "response": response,
    }


def _default_target_key(channel: str, url: str) -> str:
    return f"{channel}|{url}"


def _shadow_passed(shadow_payload: dict | None) -> bool:
    if shadow_payload is None:
        return True
    summary = shadow_payload.get("summary", {})
    if not isinstance(summary, dict):
        return False
    return bool(summary.get("passed", False))
