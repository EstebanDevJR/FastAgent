from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass
class CanaryThresholds:
    accuracy_drop_max: float = 0.03
    reasoning_drop_max: float = 0.05
    judge_drop_max: float = 0.05
    hallucinations_increase_max: float = 0.05
    cost_increase_ratio_max: float = 0.25


@dataclass
class CanaryResult:
    passed: bool
    rollback_recommended: bool
    deltas: dict[str, float]
    reasons: list[str]


def load_report_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid report JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Report file must be a JSON object")
    return payload


def compare_canary_reports(
    baseline: dict,
    candidate: dict,
    thresholds: CanaryThresholds,
    require_judge: bool = False,
) -> CanaryResult:
    reasons: list[str] = []

    base_metrics = _to_metrics(baseline)
    cand_metrics = _to_metrics(candidate)

    deltas = {
        "accuracy_drop": round(max(0.0, base_metrics["accuracy"] - cand_metrics["accuracy"]), 4),
        "reasoning_drop": round(max(0.0, base_metrics["reasoning_quality"] - cand_metrics["reasoning_quality"]), 4),
        "hallucinations_increase": round(
            max(0.0, cand_metrics["hallucinations"] - base_metrics["hallucinations"]), 4
        ),
    }

    baseline_cost = base_metrics["cost"]
    candidate_cost = cand_metrics["cost"]
    if baseline_cost <= 0:
        cost_ratio = max(0.0, candidate_cost - baseline_cost)
    else:
        cost_ratio = max(0.0, (candidate_cost - baseline_cost) / baseline_cost)
    deltas["cost_increase_ratio"] = round(cost_ratio, 4)

    baseline_judge = _to_judge_score(baseline)
    candidate_judge = _to_judge_score(candidate)
    if baseline_judge is not None and candidate_judge is not None:
        deltas["judge_drop"] = round(max(0.0, baseline_judge - candidate_judge), 4)
    elif require_judge:
        reasons.append("judge score is required but missing in one or both reports")
        deltas["judge_drop"] = 1.0

    if deltas["accuracy_drop"] > thresholds.accuracy_drop_max:
        reasons.append(f"accuracy drop {deltas['accuracy_drop']} > {thresholds.accuracy_drop_max}")
    if deltas["reasoning_drop"] > thresholds.reasoning_drop_max:
        reasons.append(f"reasoning drop {deltas['reasoning_drop']} > {thresholds.reasoning_drop_max}")
    if deltas["hallucinations_increase"] > thresholds.hallucinations_increase_max:
        reasons.append(
            f"hallucinations increase {deltas['hallucinations_increase']} > {thresholds.hallucinations_increase_max}"
        )
    if deltas["cost_increase_ratio"] > thresholds.cost_increase_ratio_max:
        reasons.append(f"cost increase ratio {deltas['cost_increase_ratio']} > {thresholds.cost_increase_ratio_max}")
    if "judge_drop" in deltas and deltas["judge_drop"] > thresholds.judge_drop_max:
        reasons.append(f"judge drop {deltas['judge_drop']} > {thresholds.judge_drop_max}")

    passed = not reasons
    return CanaryResult(
        passed=passed,
        rollback_recommended=not passed,
        deltas=deltas,
        reasons=reasons,
    )


def _to_metrics(report: dict) -> dict[str, float]:
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    return {
        "accuracy": float(metrics.get("accuracy", 0.0)),
        "reasoning_quality": float(metrics.get("reasoning_quality", 0.0)),
        "hallucinations": float(metrics.get("hallucinations", 0.0)),
        "cost": float(metrics.get("cost", 0.0)),
    }


def _to_judge_score(report: dict) -> float | None:
    judge = report.get("judge")
    if not isinstance(judge, dict):
        return None
    if "overall_score" not in judge:
        return None
    return float(judge.get("overall_score", 0.0))
