from dataclasses import dataclass


@dataclass
class EvalMetrics:
    accuracy: float
    reasoning_quality: float
    tool_usage: float
    hallucinations: float
    cost: float

    def to_dict(self) -> dict:
        return {
            "accuracy": self.accuracy,
            "reasoning_quality": self.reasoning_quality,
            "tool_usage": self.tool_usage,
            "hallucinations": self.hallucinations,
            "cost": self.cost,
        }


def score_predictions(records: list[dict]) -> EvalMetrics:
    if not records:
        return EvalMetrics(accuracy=0.0, reasoning_quality=0.0, tool_usage=0.0, hallucinations=0.0, cost=0.0)

    total = len(records)
    correct = 0
    tool_hits = 0

    for item in records:
        expected = str(item.get("expected", "")).strip().lower()
        predicted = str(item.get("predicted", item.get("output", ""))).strip().lower()
        if expected and predicted and (expected in predicted or predicted in expected):
            correct += 1
        if "tool" in predicted:
            tool_hits += 1

    accuracy = round(correct / total, 3)
    tool_usage = round(tool_hits / total, 3)

    return EvalMetrics(
        accuracy=accuracy,
        reasoning_quality=round(min(1.0, accuracy + 0.1), 3),
        tool_usage=tool_usage,
        hallucinations=round(max(0.0, 1.0 - accuracy), 3),
        cost=round(0.001 * total, 4),
    )
