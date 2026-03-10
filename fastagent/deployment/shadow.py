from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import statistics
import time


@dataclass
class ShadowSampleResult:
    message: str
    baseline_ok: bool
    candidate_ok: bool
    baseline_latency_ms: float
    candidate_latency_ms: float
    baseline_response: str
    candidate_response: str


@dataclass
class ShadowSummary:
    total: int
    baseline_error_rate: float
    candidate_error_rate: float
    disagreement_rate: float
    baseline_p95_ms: float
    candidate_p95_ms: float
    latency_increase_ratio: float
    passed: bool
    reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "baseline_error_rate": self.baseline_error_rate,
            "candidate_error_rate": self.candidate_error_rate,
            "disagreement_rate": self.disagreement_rate,
            "baseline_p95_ms": self.baseline_p95_ms,
            "candidate_p95_ms": self.candidate_p95_ms,
            "latency_increase_ratio": self.latency_increase_ratio,
            "passed": self.passed,
            "reasons": self.reasons,
        }


def load_shadow_messages(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Shadow sample file not found: {path}")

    messages: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"JSON object expected on line {line_number}")
        message = ""
        for key in ("message", "prompt", "input", "query"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                message = value.strip()
                break
        if message:
            messages.append(message)

    return messages


def simulate_shadow(
    messages: list[str],
    degradation: float = 0.15,
    seed: int = 42,
) -> list[ShadowSampleResult]:
    results: list[ShadowSampleResult] = []
    clamped_degradation = min(1.0, max(0.0, degradation))

    for message in messages:
        base_hash = _ratio(f"base|{seed}|{message}")
        cand_hash = _ratio(f"cand|{seed}|{message}")
        error_hash = _ratio(f"err|{seed}|{message}")

        baseline_latency = 40 + (base_hash * 30)
        candidate_latency = baseline_latency + (clamped_degradation * 35) + (cand_hash * 20)

        baseline_response = f"baseline:{message}"
        should_disagree = cand_hash < clamped_degradation
        candidate_response = (
            f"candidate-variant:{message[::-1]}" if should_disagree else baseline_response
        )

        candidate_ok = error_hash >= (clamped_degradation / 3.5)
        if not candidate_ok:
            candidate_response = ""

        results.append(
            ShadowSampleResult(
                message=message,
                baseline_ok=True,
                candidate_ok=candidate_ok,
                baseline_latency_ms=round(baseline_latency, 3),
                candidate_latency_ms=round(candidate_latency, 3),
                baseline_response=baseline_response,
                candidate_response=candidate_response,
            )
        )

    return results


def execute_shadow_live(
    baseline_url: str,
    candidate_url: str,
    endpoint: str,
    messages: list[str],
    timeout: float = 15.0,
) -> list[ShadowSampleResult]:
    try:
        import httpx
    except ImportError as exc:
        raise RuntimeError("httpx is required for live shadow execution") from exc

    base_target = baseline_url.rstrip("/") + endpoint
    cand_target = candidate_url.rstrip("/") + endpoint

    results: list[ShadowSampleResult] = []
    with httpx.Client(timeout=max(0.1, timeout)) as client:
        for message in messages:
            baseline_ok, baseline_latency, baseline_response = _post_message(client, base_target, message)
            candidate_ok, candidate_latency, candidate_response = _post_message(client, cand_target, message)
            results.append(
                ShadowSampleResult(
                    message=message,
                    baseline_ok=baseline_ok,
                    candidate_ok=candidate_ok,
                    baseline_latency_ms=baseline_latency,
                    candidate_latency_ms=candidate_latency,
                    baseline_response=baseline_response,
                    candidate_response=candidate_response,
                )
            )

    return results


def summarize_shadow(
    results: list[ShadowSampleResult],
    max_disagreement_rate: float = 0.25,
    max_candidate_error_rate: float = 0.1,
    max_latency_increase_ratio: float = 0.3,
) -> ShadowSummary:
    if not results:
        return ShadowSummary(
            total=0,
            baseline_error_rate=0.0,
            candidate_error_rate=0.0,
            disagreement_rate=0.0,
            baseline_p95_ms=0.0,
            candidate_p95_ms=0.0,
            latency_increase_ratio=0.0,
            passed=False,
            reasons=["no samples"],
        )

    total = len(results)
    baseline_failures = [item for item in results if not item.baseline_ok]
    candidate_failures = [item for item in results if not item.candidate_ok]
    disagreements = [
        item
        for item in results
        if item.baseline_ok
        and item.candidate_ok
        and _normalize(item.baseline_response) != _normalize(item.candidate_response)
    ]

    base_latencies = [item.baseline_latency_ms for item in results]
    cand_latencies = [item.candidate_latency_ms for item in results]
    base_p95 = _p95(base_latencies)
    cand_p95 = _p95(cand_latencies)
    latency_increase = 0.0
    if base_p95 > 0:
        latency_increase = max(0.0, (cand_p95 - base_p95) / base_p95)

    baseline_error_rate = len(baseline_failures) / total
    candidate_error_rate = len(candidate_failures) / total
    disagreement_rate = len(disagreements) / total

    reasons: list[str] = []
    if candidate_error_rate > max_candidate_error_rate:
        reasons.append(f"candidate_error_rate {round(candidate_error_rate, 4)} > {max_candidate_error_rate}")
    if disagreement_rate > max_disagreement_rate:
        reasons.append(f"disagreement_rate {round(disagreement_rate, 4)} > {max_disagreement_rate}")
    if latency_increase > max_latency_increase_ratio:
        reasons.append(f"latency_increase_ratio {round(latency_increase, 4)} > {max_latency_increase_ratio}")

    return ShadowSummary(
        total=total,
        baseline_error_rate=round(baseline_error_rate, 4),
        candidate_error_rate=round(candidate_error_rate, 4),
        disagreement_rate=round(disagreement_rate, 4),
        baseline_p95_ms=round(base_p95, 3),
        candidate_p95_ms=round(cand_p95, 3),
        latency_increase_ratio=round(latency_increase, 4),
        passed=not reasons,
        reasons=reasons,
    )


def _ratio(value: str) -> float:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    if len(values) < 20:
        return max(values)
    return statistics.quantiles(values, n=20)[18]


def _post_message(client, target: str, message: str) -> tuple[bool, float, str]:
    started = time.perf_counter()
    try:
        response = client.post(target, json={"message": message})
        latency_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            return False, round(latency_ms, 3), ""
        payload = response.json() if response.content else {}
        text = ""
        if isinstance(payload, dict):
            candidate = payload.get("response")
            if isinstance(candidate, str):
                text = candidate
        return True, round(latency_ms, 3), text
    except Exception:
        latency_ms = (time.perf_counter() - started) * 1000
        return False, round(latency_ms, 3), ""
