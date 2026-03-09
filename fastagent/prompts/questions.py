import sys

import questionary

from fastagent.architect.project_architect import ArchitectureRecommendation, recommend_architecture
from fastagent.utils.config import (
    ARCHITECT_PROVIDER_OPTIONS,
    ARCHITECT_OPENAI_MODE_OPTIONS,
    BUILD_TYPE_MAP,
    BUILD_TYPE_OPTIONS,
    LLM_PROVIDER_OPTIONS,
    MEMORY_OPTIONS,
    ProjectConfig,
    TRACING_OPTIONS,
    VECTOR_DB_OPTIONS,
)


def _select(message: str, choices: list[str], default: str) -> str:
    return questionary.select(message, choices=choices, default=default).ask() or default


def _text(message: str, default: str = "") -> str:
    return questionary.text(message, default=default).ask() or default


def _confirm(message: str, default: bool) -> bool:
    return bool(questionary.confirm(message, default=default).ask())


def _default_model_for_provider(provider: str) -> str:
    provider = provider.strip().lower()
    if provider == "openai":
        return "gpt-4o-mini"
    if provider == "ollama":
        return "llama3.1"
    return "heuristic"


def collect_project_config(
    project_name: str,
    assume_defaults: bool = False,
    project_type: str | None = None,
    description: str | None = None,
    architect_provider: str = "local",
    architect_model: str | None = None,
    architect_timeout: int = 20,
    architect_retries: int = 2,
    architect_backoff: float = 0.5,
    architect_openai_mode: str = "auto",
    architect_cache_enabled: bool = True,
    architect_cache_ttl_seconds: int = 3600,
) -> tuple[ProjectConfig, ArchitectureRecommendation]:
    if not project_name or not project_name.strip():
        raise ValueError("Project name cannot be empty")

    interactive = (not assume_defaults) and sys.stdin.isatty()

    if interactive:
        build_label = _select("What do you want to build?", BUILD_TYPE_OPTIONS, "AI Chat Agent")
        selected_type = BUILD_TYPE_MAP[build_label]
        user_description = _text("Describe your agent")
        selected_architect_provider = _select(
            "Select architect provider",
            ARCHITECT_PROVIDER_OPTIONS,
            architect_provider if architect_provider in ARCHITECT_PROVIDER_OPTIONS else "local",
        )
        default_architect_model = _default_model_for_provider(selected_architect_provider)
        selected_architect_model = _text("Architect model", default_architect_model)
        if selected_architect_provider == "openai":
            selected_openai_mode = _select(
                "OpenAI architect mode",
                ARCHITECT_OPENAI_MODE_OPTIONS,
                architect_openai_mode if architect_openai_mode in ARCHITECT_OPENAI_MODE_OPTIONS else "auto",
            )
        else:
            selected_openai_mode = "auto"
    else:
        selected_type = project_type or "chat"
        user_description = description or ""
        selected_architect_provider = architect_provider if architect_provider in ARCHITECT_PROVIDER_OPTIONS else "local"
        selected_architect_model = architect_model or _default_model_for_provider(selected_architect_provider)
        selected_openai_mode = (
            architect_openai_mode if architect_openai_mode in ARCHITECT_OPENAI_MODE_OPTIONS else "auto"
        )

    rec = recommend_architecture(
        user_description,
        None if selected_type == "custom" else selected_type,
        provider=selected_architect_provider,
        model=selected_architect_model,
        timeout=architect_timeout,
        retries=architect_retries,
        backoff_seconds=architect_backoff,
        openai_mode=selected_openai_mode if selected_architect_provider == "openai" else "auto",
        cache_enabled=architect_cache_enabled,
        cache_ttl_seconds=architect_cache_ttl_seconds,
    )

    if interactive:
        llm_provider = _select("Select LLM provider", LLM_PROVIDER_OPTIONS, "OpenAI")
        vector_default = rec.vector_db if rec.vector_db in VECTOR_DB_OPTIONS else "Qdrant"
        vector_db = _select("Select vector database", VECTOR_DB_OPTIONS, vector_default)
        memory_default = rec.memory_type if rec.memory_type in MEMORY_OPTIONS else "conversation"
        memory_type = _select("Select memory strategy", MEMORY_OPTIONS, memory_default)
        tracing_default = rec.tracing if rec.tracing in TRACING_OPTIONS else "OpenTelemetry"
        tracing = _select("Select tracing/observability", TRACING_OPTIONS, tracing_default)
        tools_csv = _text("Tools (comma separated)", ", ".join(rec.tools))
        tools = [item.strip() for item in tools_csv.split(",") if item.strip()]
        evaluation_enabled = _confirm("Enable evaluation module?", rec.evaluation_enabled)
    else:
        llm_provider = "OpenAI"
        vector_db = rec.vector_db
        memory_type = rec.memory_type
        tracing = rec.tracing
        tools = rec.tools
        evaluation_enabled = rec.evaluation_enabled

    config = ProjectConfig(
        project_name=project_name,
        project_type=rec.project_type if selected_type == "custom" else selected_type,
        description=user_description,
        llm_provider=llm_provider,
        vector_db=vector_db,
        tools=tools,
        memory_type=memory_type,
        evaluation_enabled=evaluation_enabled,
        tracing=tracing,
        suggested_models=rec.suggested_models,
        architect_provider=rec.architect_provider,
        architect_model=rec.architect_model,
        architect_openai_mode=selected_openai_mode if rec.architect_provider == "openai" else "auto",
        architect_cache_enabled=architect_cache_enabled,
        architect_cache_ttl_seconds=architect_cache_ttl_seconds,
        architect_notes=rec.notes,
    )

    return config, rec
