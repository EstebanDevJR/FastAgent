from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from urllib import error, request

PROJECT_TYPES = {"chat", "rag", "multi-agent", "tool-agent"}
VECTOR_DBS = {"None", "FAISS", "Pinecone", "Qdrant", "Weaviate"}
MEMORY_TYPES = {"conversation", "vector", "hybrid"}
TRACING_BACKENDS = {"LangSmith", "OpenTelemetry", "Prometheus", "None"}
OPENAI_MODES = {"auto", "responses", "chat"}

PROJECT_TYPE_ALIASES = {
    "multi_agent": "multi-agent",
    "multi agent": "multi-agent",
    "multiagent": "multi-agent",
    "tool": "tool-agent",
    "tools": "tool-agent",
    "tool agent": "tool-agent",
    "tool_agent": "tool-agent",
}
VECTOR_DB_ALIASES = {
    "none": "None",
    "faiss": "FAISS",
    "pinecone": "Pinecone",
    "qdrant": "Qdrant",
    "weaviate": "Weaviate",
}
TRACING_ALIASES = {
    "langsmith": "LangSmith",
    "opentelemetry": "OpenTelemetry",
    "prometheus": "Prometheus",
    "none": "None",
}
REQUIRED_RESPONSE_KEYS = {
    "project_type",
    "vector_db",
    "tools",
    "memory_type",
    "evaluation_enabled",
    "tracing",
    "suggested_models",
    "notes",
}
REMOTE_EXCEPTIONS = (ValueError, KeyError, json.JSONDecodeError, error.URLError, TimeoutError)


@dataclass
class ArchitectureRecommendation:
    project_type: str
    vector_db: str
    tools: list[str] = field(default_factory=list)
    memory_type: str = "conversation"
    evaluation_enabled: bool = True
    tracing: str = "LangSmith"
    suggested_models: list[str] = field(default_factory=lambda: ["Llama 3", "Mistral", "Phi"])
    notes: list[str] = field(default_factory=list)
    architect_provider: str = "local"
    architect_model: str = "heuristic"


def _base_recommendation(project_type: str) -> ArchitectureRecommendation:
    if project_type == "rag":
        return ArchitectureRecommendation(
            project_type="rag",
            vector_db="Qdrant",
            tools=["document_search", "context_formatter"],
            memory_type="hybrid",
            evaluation_enabled=True,
            tracing="LangSmith",
            notes=["RAG pipeline enabled with retriever abstraction."],
        )
    if project_type == "multi-agent":
        return ArchitectureRecommendation(
            project_type="multi-agent",
            vector_db="Qdrant",
            tools=["planner", "task_router", "reviewer"],
            memory_type="hybrid",
            evaluation_enabled=True,
            tracing="LangSmith",
            notes=["Planner/Worker/Reviewer pattern enabled."],
        )
    if project_type == "tool-agent":
        return ArchitectureRecommendation(
            project_type="tool-agent",
            vector_db="None",
            tools=["search_tool", "calculator_tool", "database_query"],
            memory_type="conversation",
            evaluation_enabled=True,
            tracing="OpenTelemetry",
            notes=["Tool execution layer enabled."],
        )
    return ArchitectureRecommendation(
        project_type="chat",
        vector_db="None",
        tools=["search_tool"],
        memory_type="conversation",
        evaluation_enabled=False,
        tracing="OpenTelemetry",
        notes=["Lightweight chat architecture selected."],
    )


def _heuristic_recommendation(description: str, preferred_type: str | None = None) -> ArchitectureRecommendation:
    text = (description or "").lower()

    if preferred_type and preferred_type != "custom":
        rec = _base_recommendation(preferred_type)
    elif any(word in text for word in ["multi-agent", "multi agent", "planner", "workers", "crew"]):
        rec = _base_recommendation("multi-agent")
    elif any(word in text for word in ["rag", "document", "knowledge", "pdf", "contract", "retrieval"]):
        rec = _base_recommendation("rag")
    elif any(word in text for word in ["tool", "database", "search", "calculator", "sql"]):
        rec = _base_recommendation("tool-agent")
    else:
        rec = _base_recommendation("chat")

    if any(word in text for word in ["legal", "contract", "clause"]):
        rec.project_type = "rag"
        rec.vector_db = "Qdrant"
        rec.tools = ["contract_parser", "clause_risk_analyzer", "legal_search"]
        rec.memory_type = "conversation"
        rec.evaluation_enabled = True
        rec.tracing = "LangSmith"
        rec.notes.append("Legal workflow detected: specialized contract tools suggested.")

    if any(word in text for word in ["medical", "finance", "risk", "compliance"]):
        rec.evaluation_enabled = True
        rec.notes.append("High-risk domain detected: evaluation forced on by default.")

    return rec


def _extract_json_object(text: str) -> dict:
    candidate = text.strip()
    if not candidate:
        raise ValueError("Empty architect response text")
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Prefer fenced JSON blocks first.
    fence_token = "```"
    if fence_token in candidate:
        parts = candidate.split(fence_token)
        for part in parts:
            cleaned = part.strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
            if not cleaned.startswith("{"):
                continue
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    # Scan for balanced object ranges and parse first valid dict.
    for start in range(len(candidate)):
        if candidate[start] != "{":
            continue
        depth = 0
        in_string = False
        escape = False
        for end in range(start, len(candidate)):
            ch = candidate[end]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    snippet = candidate[start : end + 1]
                    try:
                        parsed = json.loads(snippet)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        break
                    break
            if depth < 0:
                break

    raise ValueError("No JSON object found in architect response")


def _to_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False
    return default


def _to_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _canonical_project_type(value: str, fallback: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    normalized = PROJECT_TYPE_ALIASES.get(normalized, normalized)
    if normalized in PROJECT_TYPES:
        return normalized
    return fallback


def _canonical_vector_db(value: str, fallback: str) -> str:
    normalized = value.strip().lower()
    return VECTOR_DB_ALIASES.get(normalized, fallback)


def _canonical_memory(value: str, fallback: str) -> str:
    normalized = value.strip().lower()
    if normalized in MEMORY_TYPES:
        return normalized
    return fallback


def _canonical_tracing(value: str, fallback: str) -> str:
    normalized = value.strip().lower()
    return TRACING_ALIASES.get(normalized, fallback)


def _validate_required_keys(data: dict) -> None:
    missing = sorted(REQUIRED_RESPONSE_KEYS - set(data.keys()))
    if missing:
        raise ValueError(f"Architect response missing keys: {', '.join(missing)}")


def _normalize_recommendation(data: dict, fallback: ArchitectureRecommendation) -> ArchitectureRecommendation:
    _validate_required_keys(data)

    rec = ArchitectureRecommendation(
        project_type=_canonical_project_type(str(data.get("project_type", fallback.project_type)), fallback.project_type),
        vector_db=_canonical_vector_db(str(data.get("vector_db", fallback.vector_db)), fallback.vector_db),
        tools=_to_list(data.get("tools", fallback.tools)) or fallback.tools,
        memory_type=_canonical_memory(str(data.get("memory_type", fallback.memory_type)), fallback.memory_type),
        evaluation_enabled=_to_bool(data.get("evaluation_enabled", fallback.evaluation_enabled), fallback.evaluation_enabled),
        tracing=_canonical_tracing(str(data.get("tracing", fallback.tracing)), fallback.tracing),
        suggested_models=_to_list(data.get("suggested_models", fallback.suggested_models)) or fallback.suggested_models,
        notes=_to_list(data.get("notes", fallback.notes)) or fallback.notes,
    )

    return rec


def _build_architect_messages(description: str, preferred_type: str | None) -> tuple[str, str]:
    system = (
        "You are a backend architect for AI agent systems. "
        "Return only valid JSON with keys: project_type, vector_db, tools, memory_type, "
        "evaluation_enabled, tracing, suggested_models, notes."
    )
    user = (
        f"Preferred type: {preferred_type or 'auto'}\n"
        f"Description: {description or 'No description provided'}\n"
        "Choose among project_type chat|rag|multi-agent|tool-agent, "
        "vector_db None|FAISS|Pinecone|Qdrant|Weaviate, "
        "memory_type conversation|vector|hybrid, "
        "tracing LangSmith|OpenTelemetry|Prometheus|None."
    )
    return system, user


def _http_json_post(url: str, payload: dict, headers: dict[str, str], timeout: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("Remote architect response must be a JSON object")
    return parsed


def _extract_text_from_chat_completion(body: dict) -> str:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"Invalid chat completion response shape: {exc}") from exc

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks)
    raise ValueError("Unable to extract text from chat completion content")


def _extract_text_from_responses(body: dict) -> str:
    output_text = body.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = body.get("output", [])
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks)

    raise ValueError("Unable to extract text from Responses API payload")


def _recommend_via_openai_chat(description: str, preferred_type: str | None, model: str, timeout: int) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    system, user = _build_architect_messages(description, preferred_type)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    body = _http_json_post(
        url=f"{base_url}/chat/completions",
        payload=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    return _extract_json_object(_extract_text_from_chat_completion(body))


def _recommend_via_openai_responses(description: str, preferred_type: str | None, model: str, timeout: int) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured")

    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    system, user = _build_architect_messages(description, preferred_type)
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user}],
            },
        ],
        "temperature": 0.2,
    }
    body = _http_json_post(
        url=f"{base_url}/responses",
        payload=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    return _extract_json_object(_extract_text_from_responses(body))


def _recommend_via_openai(
    description: str,
    preferred_type: str | None,
    model: str,
    timeout: int,
    openai_mode: str,
) -> dict:
    mode = (openai_mode or "auto").strip().lower()
    if mode not in OPENAI_MODES:
        raise ValueError(f"Invalid openai mode '{openai_mode}'. Use one of: {', '.join(sorted(OPENAI_MODES))}")

    if mode == "chat":
        return _recommend_via_openai_chat(description, preferred_type, model, timeout)
    if mode == "responses":
        return _recommend_via_openai_responses(description, preferred_type, model, timeout)

    errors: list[str] = []
    for label, fn in (
        ("responses", _recommend_via_openai_responses),
        ("chat", _recommend_via_openai_chat),
    ):
        try:
            return fn(description, preferred_type, model, timeout)
        except REMOTE_EXCEPTIONS as exc:
            errors.append(f"{label}: {exc}")
    raise ValueError("OpenAI auto mode failed. " + "; ".join(errors))


def _recommend_via_ollama(description: str, preferred_type: str | None, model: str, timeout: int) -> dict:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    system, user = _build_architect_messages(description, preferred_type)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
    }
    body = _http_json_post(
        url=f"{base_url}/api/chat",
        payload=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    content = body.get("message", {}).get("content")
    if not isinstance(content, str):
        raise ValueError("Invalid Ollama response shape")
    return _extract_json_object(content)


def _run_with_retries(fetcher, retries: int, backoff_seconds: float):
    attempts = max(1, retries + 1)
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return fetcher()
        except REMOTE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt < attempts - 1:
                sleep_time = max(0.0, backoff_seconds) * (2**attempt)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                continue
            raise
    raise ValueError(f"Unknown architect retry failure: {last_exc}")


def _default_cache_path() -> Path:
    return Path.home() / ".fastagent" / "architect_cache.json"


def _cache_key(provider: str, model: str, preferred_type: str | None, description: str, openai_mode: str) -> str:
    payload = {
        "provider": provider,
        "model": model,
        "preferred_type": preferred_type or "",
        "description": description or "",
        "openai_mode": openai_mode,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(data, dict):
        return data
    return {}


def _save_cache(cache_path: Path, cache: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError:
        # Cache writes are best-effort and should never break recommendation generation.
        return


def _cache_get(cache_path: Path, key: str, ttl_seconds: int) -> ArchitectureRecommendation | None:
    cache = _load_cache(cache_path)
    payload = cache.get(key)
    if not isinstance(payload, dict):
        return None
    ts = payload.get("ts")
    rec_data = payload.get("recommendation")
    if not isinstance(ts, (int, float)) or not isinstance(rec_data, dict):
        return None
    if ttl_seconds > 0 and (time.time() - ts) > ttl_seconds:
        return None
    try:
        rec = ArchitectureRecommendation(**rec_data)
        if "Cache hit for architect recommendation." not in rec.notes:
            rec.notes.append("Cache hit for architect recommendation.")
        return rec
    except TypeError:
        return None


def _cache_set(cache_path: Path, key: str, rec: ArchitectureRecommendation) -> None:
    cache = _load_cache(cache_path)
    cache[key] = {"ts": time.time(), "recommendation": asdict(rec)}
    _save_cache(cache_path, cache)


def recommend_architecture(
    description: str,
    preferred_type: str | None = None,
    provider: str = "local",
    model: str | None = None,
    timeout: int = 20,
    retries: int = 2,
    backoff_seconds: float = 0.5,
    openai_mode: str = "auto",
    cache_enabled: bool = True,
    cache_ttl_seconds: int = 3600,
    cache_path: str | None = None,
) -> ArchitectureRecommendation:
    provider_normalized = (provider or "local").strip().lower()
    heuristic = _heuristic_recommendation(description, preferred_type)

    selected_model = model or ("gpt-4o-mini" if provider_normalized == "openai" else ("llama3.1" if provider_normalized == "ollama" else "heuristic"))

    cache_file = Path(cache_path) if cache_path else _default_cache_path()
    key = _cache_key(provider_normalized, selected_model, preferred_type, description, openai_mode)

    if cache_enabled:
        cached = _cache_get(cache_file, key, ttl_seconds=max(0, cache_ttl_seconds))
        if cached is not None:
            return cached

    if provider_normalized == "local":
        heuristic.architect_provider = "local"
        heuristic.architect_model = "heuristic"
        if cache_enabled:
            _cache_set(cache_file, key, heuristic)
        return heuristic

    try:
        if provider_normalized == "openai":
            raw = _run_with_retries(
                lambda: _recommend_via_openai(
                    description,
                    preferred_type,
                    selected_model,
                    timeout,
                    openai_mode=openai_mode,
                ),
                retries=retries,
                backoff_seconds=backoff_seconds,
            )
            rec = _normalize_recommendation(raw, heuristic)
            rec.architect_provider = "openai"
            rec.architect_model = selected_model
            rec.notes.append(f"Recommendation generated by OpenAI architect provider ({openai_mode} mode).")
            if cache_enabled:
                _cache_set(cache_file, key, rec)
            return rec

        if provider_normalized == "ollama":
            raw = _run_with_retries(
                lambda: _recommend_via_ollama(description, preferred_type, selected_model, timeout),
                retries=retries,
                backoff_seconds=backoff_seconds,
            )
            rec = _normalize_recommendation(raw, heuristic)
            rec.architect_provider = "ollama"
            rec.architect_model = selected_model
            rec.notes.append("Recommendation generated by Ollama architect provider.")
            if cache_enabled:
                _cache_set(cache_file, key, rec)
            return rec

        heuristic.notes.append(f"Unsupported architect provider '{provider_normalized}', using local fallback.")
    except REMOTE_EXCEPTIONS as exc:
        attempts = max(1, retries + 1)
        heuristic.notes.append(
            f"Architect provider '{provider_normalized}' failed after {attempts} attempt(s) ({exc}), using local fallback."
        )

    heuristic.architect_provider = "local"
    heuristic.architect_model = "heuristic"
    if cache_enabled:
        _cache_set(cache_file, key, heuristic)
    return heuristic
