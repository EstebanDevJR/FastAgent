from app.config.settings import settings


def trace_event(name: str, payload: dict | None = None) -> dict:
    return {
        "backend": settings.tracing_backend,
        "event": name,
        "payload": payload or {},
    }
