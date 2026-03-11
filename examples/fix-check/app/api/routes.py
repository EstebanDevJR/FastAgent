from fastapi import APIRouter, Query

from app.config.settings import settings
from app.plugins.loader import enabled_plugins
from app.plugins.policy import get_plugin_policy
from app.schemas.request import ChatRequest, ChatResponse, EvalRequest, PolicyCheckRequest
from app.services.agent_service import AgentService

router = APIRouter()
agent_service = AgentService()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/info")
def info() -> dict:
    plugins = enabled_plugins()
    plugin_policy = get_plugin_policy()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "agent_type": settings.agent_type,
        "llm_provider": settings.llm_provider,
        "router": {
            "mode": settings.router_mode,
            "providers": [item.strip() for item in settings.router_providers.split(",") if item.strip()],
        },
        "orchestration": {
            "max_retries": settings.multi_agent_max_retries,
            "max_tasks": settings.multi_agent_max_tasks,
        },
        "architect": {
            "provider": settings.architect_provider,
            "model": settings.architect_model,
            "openai_mode": settings.architect_openai_mode,
            "cache_enabled": settings.architect_cache_enabled,
            "cache_ttl": settings.architect_cache_ttl,
        },
        "plugins": {
            "count": len(plugins),
            "enabled": [plugin.get("name", "unknown") for plugin in plugins],
            "sandbox": {
                "enabled": settings.plugin_sandbox_enabled,
                "profile_default": settings.plugin_profile_default,
                "timeout_seconds": settings.plugin_timeout_seconds,
                "memory_mb": settings.plugin_memory_mb,
                "strict_timeout_seconds": settings.plugin_strict_timeout_seconds,
                "strict_memory_mb": settings.plugin_strict_memory_mb,
                "audit_enabled": settings.plugin_audit_enabled,
                "audit_log_path": settings.plugin_audit_log_path,
            },
            "policy": plugin_policy.status_summary(),
        },
        "cost_guard": {
            "enabled": settings.cost_guard_enabled,
            "cost_per_1k_tokens_usd": settings.cost_per_1k_tokens_usd,
            "session_budget_usd": settings.cost_session_budget_usd,
            "global_budget_usd": settings.cost_global_budget_usd,
            "block_on_budget": settings.cost_block_on_budget,
            "alert_threshold": settings.cost_alert_threshold,
        },
        "policy": agent_service.policy_info(),
        "tracing": {
            "backend": settings.tracing_backend,
            "trace_log_enabled": settings.trace_log_enabled,
            "trace_log_path": settings.trace_log_path,
        },
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    response = agent_service.chat(request.message, request.session_id)
    return ChatResponse(response=response)


@router.post("/evaluate")
def evaluate(request: EvalRequest) -> dict:
    return agent_service.evaluate(request.expected, request.predicted)


@router.post("/policy/check")
def policy_check(request: PolicyCheckRequest) -> dict:
    return agent_service.check_policy(message=request.message, session_id=request.session_id)


@router.get("/cost/status")
def cost_status(session_id: str | None = Query(default=None)) -> dict:
    return agent_service.cost_status(session_id=session_id)
