from dataclasses import dataclass
import json
from pathlib import Path

from fastagent.evaluation.evaluator import EvalMetrics


@dataclass
class EvalGateThresholds:
    accuracy_min: float = 0.7
    reasoning_quality_min: float = 0.7
    tool_usage_min: float = 0.0
    hallucinations_max: float = 0.4
    cost_max: float = 5.0
    judge_score_min: float = 0.0


@dataclass
class EvalGateResult:
    passed: bool
    reasons: list[str]


def load_eval_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid eval config JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Eval config must be a JSON object")
    return data


def thresholds_from_config(config: dict) -> EvalGateThresholds:
    raw = config.get("thresholds", {})
    if not isinstance(raw, dict):
        raw = {}
    return EvalGateThresholds(
        accuracy_min=float(raw.get("accuracy_min", 0.7)),
        reasoning_quality_min=float(raw.get("reasoning_quality_min", 0.7)),
        tool_usage_min=float(raw.get("tool_usage_min", 0.0)),
        hallucinations_max=float(raw.get("hallucinations_max", 0.4)),
        cost_max=float(raw.get("cost_max", 5.0)),
        judge_score_min=float(raw.get("judge_score_min", 0.0)),
    )


def evaluate_gate(
    metrics: EvalMetrics,
    thresholds: EvalGateThresholds,
    judge_score: float | None = None,
) -> EvalGateResult:
    reasons: list[str] = []

    if metrics.accuracy < thresholds.accuracy_min:
        reasons.append(f"accuracy {metrics.accuracy} < {thresholds.accuracy_min}")
    if metrics.reasoning_quality < thresholds.reasoning_quality_min:
        reasons.append(f"reasoning_quality {metrics.reasoning_quality} < {thresholds.reasoning_quality_min}")
    if metrics.tool_usage < thresholds.tool_usage_min:
        reasons.append(f"tool_usage {metrics.tool_usage} < {thresholds.tool_usage_min}")
    if metrics.hallucinations > thresholds.hallucinations_max:
        reasons.append(f"hallucinations {metrics.hallucinations} > {thresholds.hallucinations_max}")
    if metrics.cost > thresholds.cost_max:
        reasons.append(f"cost {metrics.cost} > {thresholds.cost_max}")
    if judge_score is not None and judge_score < thresholds.judge_score_min:
        reasons.append(f"judge_score {judge_score} < {thresholds.judge_score_min}")

    return EvalGateResult(passed=not reasons, reasons=reasons)
