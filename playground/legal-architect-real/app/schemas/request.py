from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str


class EvalRequest(BaseModel):
    expected: str
    predicted: str


class PolicyCheckRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None
