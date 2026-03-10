from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path


DEFAULT_AUDIT_SECRET = "fastagent-dev-audit-secret"


@dataclass
class AuditVerificationIssue:
    line: int
    reason: str


@dataclass
class AuditVerificationSummary:
    total: int
    valid: int
    invalid: int
    issues: list[AuditVerificationIssue]


def _canonical_payload(event: dict) -> bytes:
    payload = dict(event)
    payload.pop("signature", None)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sign_audit_event(event: dict, secret: str) -> str:
    key = (secret or DEFAULT_AUDIT_SECRET).encode("utf-8")
    digest = hmac.new(key, _canonical_payload(event), hashlib.sha256).hexdigest()
    return digest


def verify_audit_event(event: dict, secret: str) -> bool:
    if not isinstance(event, dict):
        return False
    signature = str(event.get("signature", "")).strip()
    if not signature:
        return False
    expected = sign_audit_event(event, secret=secret)
    return hmac.compare_digest(signature, expected)


def verify_audit_log(log_file: Path, secret: str, strict_schema: bool = False) -> AuditVerificationSummary:
    if not log_file.exists():
        raise FileNotFoundError(f"Audit log not found: {log_file}")

    total = 0
    valid = 0
    issues: list[AuditVerificationIssue] = []

    for line_number, line in enumerate(log_file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        total += 1
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            issues.append(AuditVerificationIssue(line=line_number, reason=f"invalid_json:{exc}"))
            continue

        if strict_schema:
            missing = _missing_fields(item, {"timestamp", "plugin", "module", "status", "signature"})
            if missing:
                issues.append(AuditVerificationIssue(line=line_number, reason=f"missing_fields:{','.join(missing)}"))
                continue

        if verify_audit_event(item, secret=secret):
            valid += 1
        else:
            issues.append(AuditVerificationIssue(line=line_number, reason="bad_signature"))

    return AuditVerificationSummary(
        total=total,
        valid=valid,
        invalid=len(issues),
        issues=issues,
    )


def _missing_fields(event: object, required: set[str]) -> list[str]:
    if not isinstance(event, dict):
        return sorted(required)
    missing = [name for name in sorted(required) if not str(event.get(name, "")).strip()]
    return missing
