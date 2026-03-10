from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import time


@dataclass
class TraceEvent:
    line: int
    timestamp: str
    event: str
    backend: str
    payload: dict
    raw: dict


@dataclass
class ReplayResult:
    index: int
    message: str
    ok: bool
    status_code: int
    latency_ms: float
    error: str


def load_trace_events(trace_file: Path, limit: int | None = None) -> list[TraceEvent]:
    if not trace_file.exists():
        raise FileNotFoundError(f"Trace file not found: {trace_file}")

    events: list[TraceEvent] = []
    for line_number, line in enumerate(trace_file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            item = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"Trace line {line_number} must be a JSON object")

        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            payload = {"value": payload}

        events.append(
            TraceEvent(
                line=line_number,
                timestamp=str(item.get("timestamp", "")),
                event=str(item.get("event", item.get("name", "unknown"))),
                backend=str(item.get("backend", "unknown")),
                payload=payload,
                raw=item,
            )
        )
        if limit is not None and limit > 0 and len(events) >= limit:
            break

    return events


def extract_chat_messages(events: list[TraceEvent], event_name: str = "chat_request") -> list[str]:
    messages: list[str] = []
    target = event_name.strip().lower()

    for event in events:
        if target and event.event.strip().lower() != target:
            continue
        for key in ("message", "prompt", "input", "query", "text"):
            value = event.payload.get(key)
            if isinstance(value, str) and value.strip():
                messages.append(value.strip())
                break
        else:
            request = event.payload.get("request")
            if isinstance(request, dict):
                msg = request.get("message")
                if isinstance(msg, str) and msg.strip():
                    messages.append(msg.strip())

    return messages


async def _post_message(client, url: str, message: str, timeout: float, index: int) -> ReplayResult:
    start = time.perf_counter()
    try:
        response = await client.post(url, json={"message": message}, timeout=timeout)
        latency_ms = (time.perf_counter() - start) * 1000
        return ReplayResult(
            index=index,
            message=message,
            ok=response.status_code < 400,
            status_code=response.status_code,
            latency_ms=latency_ms,
            error="",
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return ReplayResult(
            index=index,
            message=message,
            ok=False,
            status_code=0,
            latency_ms=latency_ms,
            error=str(exc),
        )


async def replay_messages(
    base_url: str,
    endpoint: str,
    messages: list[str],
    concurrency: int = 5,
    timeout: float = 15.0,
) -> list[ReplayResult]:
    import httpx

    semaphore = asyncio.Semaphore(max(1, concurrency))
    url = base_url.rstrip("/") + endpoint

    async with httpx.AsyncClient() as client:
        async def _wrapped(msg: str, idx: int) -> ReplayResult:
            async with semaphore:
                return await _post_message(client, url=url, message=msg, timeout=timeout, index=idx)

        tasks = [_wrapped(msg, idx) for idx, msg in enumerate(messages, start=1)]
        return await asyncio.gather(*tasks)
