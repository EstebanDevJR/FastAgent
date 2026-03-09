from fastagent.architect import project_architect
from fastagent.architect.project_architect import recommend_architecture


def test_recommend_architecture_for_legal_contracts() -> None:
    rec = recommend_architecture("I want an AI that analyzes legal contracts for SMEs")
    assert rec.project_type == "rag"
    assert rec.vector_db == "Qdrant"
    assert "contract_parser" in rec.tools


def test_recommend_architecture_for_multi_agent_request() -> None:
    rec = recommend_architecture("Need multi-agent planner workers reviewer")
    assert rec.project_type == "multi-agent"
    assert rec.evaluation_enabled is True


def test_recommend_architecture_unsupported_provider_falls_back_to_local() -> None:
    rec = recommend_architecture("simple chat", provider="unsupported")
    assert rec.architect_provider == "local"
    assert any("fallback" in note.lower() for note in rec.notes)


def test_recommend_architecture_openai_without_key_falls_back_to_local() -> None:
    rec = recommend_architecture("simple chat", provider="openai", model="gpt-4o-mini", timeout=1, retries=0)
    assert rec.architect_provider == "local"


def test_openai_retry_then_success(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_openai(description: str, preferred_type: str | None, model: str, timeout: int, openai_mode: str) -> dict:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("temporary failure")
        return {
            "project_type": "rag",
            "vector_db": "qdrant",
            "tools": ["doc_search"],
            "memory_type": "hybrid",
            "evaluation_enabled": "true",
            "tracing": "langsmith",
            "suggested_models": ["Llama 3"],
            "notes": ["ok"],
        }

    monkeypatch.setattr(project_architect, "_recommend_via_openai", fake_openai)

    rec = recommend_architecture(
        "rag over docs",
        provider="openai",
        model="gpt-4o-mini",
        retries=1,
        backoff_seconds=0,
        cache_enabled=False,
    )

    assert calls["count"] == 2
    assert rec.architect_provider == "openai"
    assert rec.vector_db == "Qdrant"
    assert rec.evaluation_enabled is True


def test_openai_invalid_payload_falls_back_to_local(monkeypatch) -> None:
    def fake_openai(description: str, preferred_type: str | None, model: str, timeout: int, openai_mode: str) -> dict:
        return {"project_type": "rag"}

    monkeypatch.setattr(project_architect, "_recommend_via_openai", fake_openai)

    rec = recommend_architecture(
        "rag over docs",
        provider="openai",
        model="gpt-4o-mini",
        retries=0,
        cache_enabled=False,
    )

    assert rec.architect_provider == "local"
    assert any("missing keys" in note.lower() for note in rec.notes)


def test_openai_mode_invalid_falls_back_to_local() -> None:
    rec = recommend_architecture("test", provider="openai", openai_mode="invalid", retries=0, cache_enabled=False)
    assert rec.architect_provider == "local"
    assert any("invalid openai mode" in note.lower() for note in rec.notes)


def test_architect_cache_hit(monkeypatch, tmp_path) -> None:
    calls = {"count": 0}

    def fake_openai(description: str, preferred_type: str | None, model: str, timeout: int, openai_mode: str) -> dict:
        calls["count"] += 1
        return {
            "project_type": "chat",
            "vector_db": "None",
            "tools": ["search_tool"],
            "memory_type": "conversation",
            "evaluation_enabled": False,
            "tracing": "OpenTelemetry",
            "suggested_models": ["Llama 3"],
            "notes": ["from remote"],
        }

    monkeypatch.setattr(project_architect, "_recommend_via_openai", fake_openai)
    cache_file = tmp_path / "architect_cache.json"

    rec1 = recommend_architecture(
        "cached query",
        provider="openai",
        model="gpt-4o-mini",
        retries=0,
        cache_enabled=True,
        cache_path=str(cache_file),
    )
    rec2 = recommend_architecture(
        "cached query",
        provider="openai",
        model="gpt-4o-mini",
        retries=0,
        cache_enabled=True,
        cache_path=str(cache_file),
    )

    assert rec1.architect_provider == "openai"
    assert rec2.architect_provider == "openai"
    assert calls["count"] == 1
    assert any("cache hit" in note.lower() for note in rec2.notes)
