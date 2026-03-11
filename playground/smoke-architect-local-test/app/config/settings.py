from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "smoke-architect-local-test")
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_type: str = os.getenv("AGENT_TYPE", "rag")
    llm_provider: str = os.getenv("LLM_PROVIDER", "OpenAI")
    llm_request_timeout: float = float(os.getenv("LLM_REQUEST_TIMEOUT", "20"))
    llm_allow_local_fallback: bool = os.getenv("LLM_ALLOW_LOCAL_FALLBACK", "true").lower() == "true"
    router_mode: str = os.getenv("ROUTER_MODE", "balanced")
    router_providers: str = os.getenv("ROUTER_PROVIDERS", "OpenAI,Anthropic,Google DeepMind,Meta AI")
    multi_agent_max_retries: int = int(os.getenv("MULTI_AGENT_MAX_RETRIES", "2"))
    multi_agent_max_tasks: int = int(os.getenv("MULTI_AGENT_MAX_TASKS", "4"))
    vector_db: str = os.getenv("VECTOR_DB", "Qdrant")
    memory_type: str = os.getenv("MEMORY_TYPE", "conversation")
    memory_vector_dimensions: int = int(os.getenv("MEMORY_VECTOR_DIMENSIONS", "128"))
    memory_vector_top_k: int = int(os.getenv("MEMORY_VECTOR_TOP_K", "8"))
    memory_recency_window: int = int(os.getenv("MEMORY_RECENCY_WINDOW", "6"))
    tracing_backend: str = os.getenv("TRACING_BACKEND", "LangSmith")
    trace_log_enabled: bool = os.getenv("TRACE_LOG_ENABLED", "true").lower() == "true"
    trace_log_path: str = os.getenv("TRACE_LOG_PATH", "logs/traces.jsonl")
    plugin_sandbox_enabled: bool = os.getenv("PLUGIN_SANDBOX_ENABLED", "true").lower() == "true"
    plugin_profile_default: str = os.getenv("PLUGIN_PROFILE_DEFAULT", "balanced")
    plugin_timeout_seconds: float = float(os.getenv("PLUGIN_TIMEOUT_SECONDS", "2.0"))
    plugin_memory_mb: int = int(os.getenv("PLUGIN_MEMORY_MB", "256"))
    plugin_strict_timeout_seconds: float = float(os.getenv("PLUGIN_STRICT_TIMEOUT_SECONDS", "1.0"))
    plugin_strict_memory_mb: int = int(os.getenv("PLUGIN_STRICT_MEMORY_MB", "128"))
    plugin_audit_enabled: bool = os.getenv("PLUGIN_AUDIT_ENABLED", "true").lower() == "true"
    plugin_audit_log_path: str = os.getenv("PLUGIN_AUDIT_LOG_PATH", "logs/plugin_audit.jsonl")
    plugin_audit_secret: str = os.getenv("PLUGIN_AUDIT_SECRET", "fastagent-dev-audit-secret")
    plugin_policy_enabled: bool = os.getenv("PLUGIN_POLICY_ENABLED", "true").lower() == "true"
    plugin_allowed: str = os.getenv("PLUGIN_ALLOWED", "")
    plugin_denied: str = os.getenv("PLUGIN_DENIED", "")
    plugin_max_calls_per_request: int = int(os.getenv("PLUGIN_MAX_CALLS_PER_REQUEST", "3"))
    plugin_circuit_failure_threshold: int = int(os.getenv("PLUGIN_CIRCUIT_FAILURE_THRESHOLD", "3"))
    plugin_circuit_cooldown_seconds: float = float(os.getenv("PLUGIN_CIRCUIT_COOLDOWN_SECONDS", "30"))
    cost_guard_enabled: bool = os.getenv("COST_GUARD_ENABLED", "true").lower() == "true"
    cost_per_1k_tokens_usd: float = float(os.getenv("COST_PER_1K_TOKENS_USD", "0.002"))
    cost_session_budget_usd: float = float(os.getenv("COST_SESSION_BUDGET_USD", "0.05"))
    cost_global_budget_usd: float = float(os.getenv("COST_GLOBAL_BUDGET_USD", "10"))
    cost_block_on_budget: bool = os.getenv("COST_BLOCK_ON_BUDGET", "true").lower() == "true"
    cost_alert_threshold: float = float(os.getenv("COST_ALERT_THRESHOLD", "0.8"))
    evaluation_enabled: bool = os.getenv("EVALUATION_ENABLED", "true").lower() == "true"
    policy_enabled: bool = os.getenv("POLICY_ENABLED", "true").lower() == "true"
    policy_file: str = os.getenv("POLICY_FILE", "app/policy/policies.json")
    architect_provider: str = os.getenv("ARCHITECT_PROVIDER", "local")
    architect_model: str = os.getenv("ARCHITECT_MODEL", "heuristic")
    architect_openai_mode: str = os.getenv("ARCHITECT_OPENAI_MODE", "auto")
    architect_cache_enabled: bool = os.getenv("ARCHITECT_CACHE_ENABLED", "false").lower() == "true"
    architect_cache_ttl: int = int(os.getenv("ARCHITECT_CACHE_TTL", "3600"))
    architect_timeout: int = int(os.getenv("ARCHITECT_TIMEOUT", "20"))
    architect_retries: int = int(os.getenv("ARCHITECT_RETRIES", "2"))
    architect_backoff: float = float(os.getenv("ARCHITECT_BACKOFF", "0.5"))
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_base_url: str = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_base_url: str = os.getenv("GOOGLE_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    google_model: str = os.getenv("GOOGLE_MODEL", "gemini-1.5-flash")
    meta_model: str = os.getenv("META_MODEL", "llama3.1")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    app_db_path: str = os.getenv("APP_DB_PATH", "data/app.db")
    app_db_max_rows: int = int(os.getenv("APP_DB_MAX_ROWS", "20"))


settings = Settings()
