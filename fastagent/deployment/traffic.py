from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess


@dataclass
class TrafficApplyPlan:
    action: str
    current_phase: int
    target_weight: int
    provider: str
    resource: str
    namespace: str
    command: list[str] | None = None
    patch: dict | None = None

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "current_phase": self.current_phase,
            "target_weight": self.target_weight,
            "provider": self.provider,
            "resource": self.resource,
            "namespace": self.namespace,
            "command": self.command,
            "patch": self.patch,
        }


def load_rollout_decision_report(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Decision report not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid decision report JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Decision report must be a JSON object")
    return payload


def target_weight_from_report(report: dict) -> tuple[str, int, int]:
    decision = report.get("decision", {})
    state = report.get("state", {})
    if not isinstance(decision, dict):
        decision = {}
    if not isinstance(state, dict):
        state = {}

    action = str(decision.get("action", "hold")).strip().lower() or "hold"
    current_phase = int(decision.get("current_phase", state.get("current_phase", 0)))
    next_phase = int(decision.get("next_phase", current_phase))

    if action == "rollback":
        weight = 0
    elif action in {"advance", "complete"}:
        weight = next_phase
    else:
        weight = current_phase

    return action, current_phase, max(0, min(100, int(weight)))


def build_argo_command(
    rollout_name: str,
    weight: int,
    namespace: str = "default",
    kubectl_bin: str = "kubectl",
    kube_context: str = "",
) -> list[str]:
    cmd = [kubectl_bin]
    if kube_context.strip():
        cmd.extend(["--context", kube_context.strip()])
    cmd.extend(
        [
            "argo",
            "rollouts",
            "set",
            "weight",
            rollout_name,
            str(weight),
            "-n",
            namespace,
        ]
    )
    return cmd


def build_gateway_patch(
    baseline_backend: str,
    candidate_backend: str,
    candidate_weight: int,
) -> dict:
    baseline_weight = max(0, 100 - candidate_weight)
    return {
        "spec": {
            "rules": [
                {
                    "backendRefs": [
                        {"name": baseline_backend, "weight": baseline_weight},
                        {"name": candidate_backend, "weight": candidate_weight},
                    ]
                }
            ]
        }
    }


def build_gateway_patch_command(
    route_name: str,
    namespace: str,
    patch: dict,
    kubectl_bin: str = "kubectl",
    kube_context: str = "",
) -> list[str]:
    cmd = [kubectl_bin]
    if kube_context.strip():
        cmd.extend(["--context", kube_context.strip()])
    cmd.extend(
        [
            "-n",
            namespace,
            "patch",
            "httproute",
            route_name,
            "--type",
            "merge",
            "-p",
            json.dumps(patch, separators=(",", ":")),
        ]
    )
    return cmd


def execute_command(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, capture_output=True, text=True)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
