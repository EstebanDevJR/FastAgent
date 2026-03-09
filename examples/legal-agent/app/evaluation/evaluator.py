def evaluate_response(expected: str, predicted: str) -> dict:
    expected_norm = expected.strip().lower()
    predicted_norm = predicted.strip().lower()
    accuracy = 1.0 if expected_norm and predicted_norm and (expected_norm in predicted_norm or predicted_norm in expected_norm) else 0.0

    return {
        "accuracy": accuracy,
        "reasoning_quality": min(1.0, accuracy + 0.2),
        "tool_usage": 1.0 if "tool" in predicted_norm else 0.0,
        "hallucinations": 0.0 if accuracy > 0 else 1.0,
        "cost": 0.001,
    }
