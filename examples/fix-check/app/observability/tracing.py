from datetime import datetime, timezone
import json
from pathlib import Path

from app.config.settings import settings


def trace_event(name: str, payload: dict | None = None) -> dict:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "backend": settings.tracing_backend,
        "event": name,
        "payload": payload or {},
    }

    if settings.trace_log_enabled:
        try:
            path = Path(settings.trace_log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError as exc:
            event["log_error"] = str(exc)

    return event
