from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


@dataclass
class RolloutState:
    current_phase: int
    plan: list[int]
    status: str
    history: list[dict]

    def to_dict(self) -> dict:
        return {
            "current_phase": self.current_phase,
            "plan": self.plan,
            "status": self.status,
            "history": self.history,
        }


@dataclass
class RolloutDecision:
    action: str
    current_phase: int
    next_phase: int
    passed: bool
    reasons: list[str]
    rollback_recommended: bool
    adaptive: bool = False
    risk_score: float = 0.0
    phase_step: int = 1

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "current_phase": self.current_phase,
            "next_phase": self.next_phase,
            "passed": self.passed,
            "reasons": self.reasons,
            "rollback_recommended": self.rollback_recommended,
            "adaptive": self.adaptive,
            "risk_score": self.risk_score,
            "phase_step": self.phase_step,
        }


def parse_phase_plan(plan: str) -> list[int]:
    values: list[int] = []
    seen = set()
    for raw in plan.split(","):
        text = raw.strip()
        if not text:
            continue
        value = int(text)
        if value <= 0:
            continue
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    values.sort()
    if not values:
        raise ValueError("Phase plan must include at least one positive integer phase")
    return values


def load_rollout_state(path: Path, plan: list[int]) -> RolloutState:
    if not path.exists():
        return RolloutState(current_phase=0, plan=plan, status="initialized", history=[])

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid rollout state JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Rollout state must be a JSON object")

    history = payload.get("history", [])
    if not isinstance(history, list):
        history = []

    return RolloutState(
        current_phase=int(payload.get("current_phase", 0)),
        plan=plan,
        status=str(payload.get("status", "initialized")).strip() or "initialized",
        history=[item for item in history if isinstance(item, dict)],
    )


def save_rollout_state(path: Path, state: RolloutState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")


def evaluate_rollout_reports(
    canary_report: dict | None = None,
    shadow_report: dict | None = None,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    checks = 0

    if canary_report is not None:
        checks += 1
        canary_pass = bool(canary_report.get("passed", False))
        if not canary_pass:
            reasons.append("canary_check_failed")

    if shadow_report is not None:
        checks += 1
        summary = shadow_report.get("summary", shadow_report)
        if not isinstance(summary, dict):
            reasons.append("shadow_report_invalid")
        else:
            shadow_pass = bool(summary.get("passed", False))
            if not shadow_pass:
                reasons.append("shadow_check_failed")

    if checks == 0:
        reasons.append("no_reports_provided")

    return (not reasons), reasons


def estimate_rollout_risk(
    canary_report: dict | None = None,
    shadow_report: dict | None = None,
) -> float:
    scores: list[float] = []
    weights: list[float] = []

    canary_score = _canary_risk_score(canary_report)
    if canary_score is not None:
        scores.append(canary_score)
        weights.append(0.6)

    shadow_score = _shadow_risk_score(shadow_report)
    if shadow_score is not None:
        scores.append(shadow_score)
        weights.append(0.4)

    if not scores:
        return 0.5
    weighted = sum(score * weight for score, weight in zip(scores, weights))
    total_weight = sum(weights) or 1.0
    return round(min(1.0, max(0.0, weighted / total_weight)), 4)


def decide_rollout(
    state: RolloutState,
    passed: bool,
    reasons: list[str],
    target_phase: int,
    adaptive: bool = False,
    risk_score: float = 0.0,
    min_phase_increment: int = 1,
    max_phase_increment: int = 2,
    stability_window: int = 2,
    hold_risk_threshold: float = 0.7,
) -> RolloutDecision:
    current = state.current_phase
    plan = [phase for phase in state.plan if phase <= target_phase]
    if target_phase not in plan and target_phase > 0:
        plan.append(target_phase)
        plan = sorted(set(plan))

    if not passed:
        return RolloutDecision(
            action="rollback",
            current_phase=current,
            next_phase=current,
            passed=False,
            reasons=reasons,
            rollback_recommended=True,
            adaptive=adaptive,
            risk_score=risk_score,
            phase_step=0,
        )

    if current >= target_phase:
        return RolloutDecision(
            action="complete",
            current_phase=current,
            next_phase=current,
            passed=True,
            reasons=[],
            rollback_recommended=False,
            adaptive=adaptive,
            risk_score=risk_score,
            phase_step=0,
        )

    next_candidates = [phase for phase in plan if phase > current]
    if not next_candidates:
        return RolloutDecision(
            action="hold",
            current_phase=current,
            next_phase=current,
            passed=True,
            reasons=["no_next_phase"],
            rollback_recommended=False,
            adaptive=adaptive,
            risk_score=risk_score,
            phase_step=0,
        )

    phase_step = max(1, min_phase_increment)
    if adaptive:
        if risk_score >= hold_risk_threshold:
            return RolloutDecision(
                action="hold",
                current_phase=current,
                next_phase=current,
                passed=True,
                reasons=["adaptive_risk_high"],
                rollback_recommended=False,
                adaptive=True,
                risk_score=risk_score,
                phase_step=0,
            )

        streak = _success_streak(state.history)
        max_jump = max(phase_step, max_phase_increment)
        if risk_score <= 0.2 and streak >= max(1, stability_window):
            phase_step = max_jump
        elif risk_score <= 0.4 and streak >= 1:
            phase_step = min(max_jump, phase_step + 1)

    idx = min(len(next_candidates) - 1, phase_step - 1)
    next_phase = next_candidates[idx]
    return RolloutDecision(
        action="advance",
        current_phase=current,
        next_phase=next_phase,
        passed=True,
        reasons=[],
        rollback_recommended=False,
        adaptive=adaptive,
        risk_score=risk_score,
        phase_step=phase_step,
    )


def apply_rollout_decision(state: RolloutState, decision: RolloutDecision, deployment_id: str) -> RolloutState:
    timestamp = datetime.now(timezone.utc).isoformat()
    history_item = {
        "timestamp": timestamp,
        "deployment_id": deployment_id,
        "action": decision.action,
        "current_phase": decision.current_phase,
        "next_phase": decision.next_phase,
        "passed": decision.passed,
        "reasons": decision.reasons,
        "rollback_recommended": decision.rollback_recommended,
        "adaptive": decision.adaptive,
        "risk_score": decision.risk_score,
        "phase_step": decision.phase_step,
    }
    state.history.append(history_item)

    if decision.action == "advance":
        state.current_phase = decision.next_phase
        state.status = f"advanced_to_{decision.next_phase}"
    elif decision.action == "complete":
        state.status = "complete"
    elif decision.action == "rollback":
        state.status = "rollback_recommended"
    else:
        state.status = "hold"

    return state


def _canary_risk_score(canary_report: dict | None) -> float | None:
    if not isinstance(canary_report, dict):
        return None
    if not bool(canary_report.get("passed", False)):
        return 1.0

    deltas = canary_report.get("deltas", {})
    if not isinstance(deltas, dict):
        return 0.5

    terms: list[float] = []
    _add_ratio(terms, deltas.get("accuracy_drop"), 0.03)
    _add_ratio(terms, deltas.get("reasoning_drop"), 0.05)
    _add_ratio(terms, deltas.get("judge_drop"), 0.05)
    _add_ratio(terms, deltas.get("hallucinations_increase"), 0.05)
    _add_ratio(terms, deltas.get("cost_increase_ratio"), 0.25)
    if not terms:
        return 0.2
    return min(1.0, max(0.0, sum(terms) / len(terms)))


def _shadow_risk_score(shadow_report: dict | None) -> float | None:
    if not isinstance(shadow_report, dict):
        return None
    summary = shadow_report.get("summary", shadow_report)
    if not isinstance(summary, dict):
        return 1.0
    if not bool(summary.get("passed", False)):
        return 1.0

    terms: list[float] = []
    _add_ratio(terms, summary.get("candidate_error_rate"), 0.1)
    _add_ratio(terms, summary.get("disagreement_rate"), 0.25)
    _add_ratio(terms, summary.get("latency_increase_ratio"), 0.3)
    if not terms:
        return 0.2
    return min(1.0, max(0.0, sum(terms) / len(terms)))


def _add_ratio(bucket: list[float], value: object, scale: float) -> None:
    if scale <= 0:
        return
    try:
        v = float(value)
    except (TypeError, ValueError):
        return
    bucket.append(min(1.0, max(0.0, v / scale)))


def _success_streak(history: list[dict]) -> int:
    streak = 0
    for item in reversed(history):
        if not isinstance(item, dict):
            break
        if item.get("action") in {"advance", "complete"} and bool(item.get("passed", False)):
            streak += 1
            continue
        break
    return streak
