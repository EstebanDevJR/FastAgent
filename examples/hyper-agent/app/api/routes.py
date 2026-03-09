from fastapi import APIRouter

from app.config.settings import settings
from app.plugins.loader import enabled_plugins
from app.schemas.request import ChatRequest, ChatResponse, EvalRequest
from app.services.agent_service import AgentService

router = APIRouter()
agent_service = AgentService()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/info")
def info() -> dict:
    plugins = enabled_plugins()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "agent_type": settings.agent_type,
        "llm_provider": settings.llm_provider,
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
        },
    }


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    response = agent_service.chat(request.message, request.session_id)
    return ChatResponse(response=response)


@router.post("/evaluate")
def evaluate(request: EvalRequest) -> dict:
    return agent_service.evaluate(request.expected, request.predicted)
