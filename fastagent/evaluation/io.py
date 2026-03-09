import json
from pathlib import Path


def load_jsonl_records(dataset: Path) -> list[dict]:
    if not dataset.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset}")

    records: list[dict] = []
    for line_number, line in enumerate(dataset.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"JSON object expected on line {line_number}")
        records.append(item)

    return records

