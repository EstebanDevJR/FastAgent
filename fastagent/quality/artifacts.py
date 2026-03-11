from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


SUPPORTED_ARTIFACTS = {
    "eval_config",
    "eval_report",
    "canary_report",
    "shadow_report",
    "rollout_decision",
    "autopilot_report",
    "plugin_registry",
}


@dataclass
class ArtifactValidationResult:
    artifact_type: str
    path: str
    valid: bool
    errors: list[str]

    def to_dict(self) -> dict:
        return {
            "artifact_type": self.artifact_type,
            "path": self.path,
            "valid": self.valid,
            "errors": self.errors,
        }


def validate_artifact_file(artifact_type: str, path: Path) -> ArtifactValidationResult:
    normalized = artifact_type.strip().lower()
    if normalized not in SUPPORTED_ARTIFACTS:
        return ArtifactValidationResult(
            artifact_type=normalized,
            path=str(path),
            valid=False,
            errors=[f"unsupported artifact type: {artifact_type}"],
        )
    if not path.exists():
        return ArtifactValidationResult(
            artifact_type=normalized,
            path=str(path),
            valid=False,
            errors=[f"file not found: {path}"],
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return ArtifactValidationResult(
            artifact_type=normalized,
            path=str(path),
            valid=False,
            errors=[f"invalid JSON: {exc}"],
        )

    errors = _validate_payload(normalized, payload)
    return ArtifactValidationResult(
        artifact_type=normalized,
        path=str(path),
        valid=not errors,
        errors=errors,
    )


def _validate_payload(artifact_type: str, payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["artifact must be a JSON object"]

    if artifact_type == "eval_config":
        return _validate_eval_config(payload)
    if artifact_type == "eval_report":
        return _validate_eval_report(payload)
    if artifact_type == "canary_report":
        return _validate_canary_report(payload)
    if artifact_type == "shadow_report":
        return _validate_shadow_report(payload)
    if artifact_type == "rollout_decision":
        return _validate_rollout_decision(payload)
    if artifact_type == "autopilot_report":
        return _validate_autopilot_report(payload)
    if artifact_type == "plugin_registry":
        return _validate_plugin_registry(payload)

    return [f"unsupported artifact type: {artifact_type}"]


def _validate_eval_config(payload: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload.get("dataset"), str) or not str(payload.get("dataset", "")).strip():
        errors.append("dataset is required and must be a non-empty string")
    thresholds = payload.get("thresholds")
    if thresholds is not None and not isinstance(thresholds, dict):
        errors.append("thresholds must be an object if provided")
    return errors


def _validate_eval_report(payload: dict) -> list[str]:
    errors: list[str] = []
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("metrics object is required")
        return errors
    for key in ("accuracy", "reasoning_quality", "tool_usage", "hallucinations", "cost"):
        if key not in metrics:
            errors.append(f"metrics.{key} is required")
            continue
        try:
            float(metrics[key])
        except (TypeError, ValueError):
            errors.append(f"metrics.{key} must be numeric")
    return errors


def _validate_canary_report(payload: dict) -> list[str]:
    errors: list[str] = []
    if "passed" not in payload or not isinstance(payload.get("passed"), bool):
        errors.append("passed is required and must be boolean")
    if "rollback_recommended" not in payload or not isinstance(payload.get("rollback_recommended"), bool):
        errors.append("rollback_recommended is required and must be boolean")
    if "deltas" not in payload or not isinstance(payload.get("deltas"), dict):
        errors.append("deltas is required and must be object")
    if "reasons" not in payload or not isinstance(payload.get("reasons"), list):
        errors.append("reasons is required and must be array")
    return errors


def _validate_shadow_report(payload: dict) -> list[str]:
    errors: list[str] = []
    summary = payload.get("summary", payload)
    if not isinstance(summary, dict):
        return ["summary must be an object"]
    required = ("passed", "total", "candidate_error_rate", "disagreement_rate", "latency_increase_ratio")
    for key in required:
        if key not in summary:
            errors.append(f"summary.{key} is required")
    if "passed" in summary and not isinstance(summary.get("passed"), bool):
        errors.append("summary.passed must be boolean")
    for key in ("total",):
        if key in summary:
            try:
                int(summary[key])
            except (TypeError, ValueError):
                errors.append(f"summary.{key} must be integer")
    for key in ("candidate_error_rate", "disagreement_rate", "latency_increase_ratio"):
        if key in summary:
            try:
                float(summary[key])
            except (TypeError, ValueError):
                errors.append(f"summary.{key} must be numeric")
    return errors


def _validate_rollout_decision(payload: dict) -> list[str]:
    errors: list[str] = []
    decision = payload.get("decision")
    state = payload.get("state")
    if not isinstance(decision, dict):
        errors.append("decision object is required")
    else:
        for key in ("action", "current_phase", "next_phase", "rollback_recommended"):
            if key not in decision:
                errors.append(f"decision.{key} is required")
    if not isinstance(state, dict):
        errors.append("state object is required")
    else:
        if "current_phase" not in state:
            errors.append("state.current_phase is required")
    return errors


def _validate_autopilot_report(payload: dict) -> list[str]:
    errors: list[str] = []
    for key in ("canary", "decision", "state", "apply", "approval", "webhook"):
        if key not in payload:
            errors.append(f"{key} is required")
        elif not isinstance(payload.get(key), dict):
            errors.append(f"{key} must be an object")
    return errors


def _validate_plugin_registry(payload: dict) -> list[str]:
    errors: list[str] = []
    plugins = payload.get("plugins")
    if not isinstance(plugins, list):
        return ["plugins array is required"]
    for idx, item in enumerate(plugins):
        if not isinstance(item, dict):
            errors.append(f"plugins[{idx}] must be object")
            continue
        for key in ("name", "sha256"):
            if key not in item:
                errors.append(f"plugins[{idx}].{key} is required")
        has_location = False
        for location_key in ("url", "source", "module", "filename"):
            value = item.get(location_key)
            if isinstance(value, str) and value.strip():
                has_location = True
                break
        if not has_location:
            errors.append(f"plugins[{idx}] must include one location field: url|source|module|filename")
    return errors
