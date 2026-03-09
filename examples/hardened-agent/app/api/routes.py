from fastapi import APIRouter

from app.schemas.request import ChatRequest, ChatResponse, EvalRequest
from app.services.agent_service import AgentService

router = APIRouter()
agent_service = AgentService()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    response = agent_service.chat(request.message, request.session_id)
    return ChatResponse(response=response)


@router.post("/evaluate")
def evaluate(request: EvalRequest) -> dict:
    return agent_service.evaluate(request.expected, request.predicted)
