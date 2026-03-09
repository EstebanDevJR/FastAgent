from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "hardened-agent")
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_type: str = os.getenv("AGENT_TYPE", "rag")
    llm_provider: str = os.getenv("LLM_PROVIDER", "OpenAI")
    vector_db: str = os.getenv("VECTOR_DB", "Qdrant")
    memory_type: str = os.getenv("MEMORY_TYPE", "conversation")
    tracing_backend: str = os.getenv("TRACING_BACKEND", "LangSmith")
    evaluation_enabled: bool = os.getenv("EVALUATION_ENABLED", "true").lower() == "true"
    architect_provider: str = os.getenv("ARCHITECT_PROVIDER", "local")
    architect_model: str = os.getenv("ARCHITECT_MODEL", "heuristic")
    architect_timeout: int = int(os.getenv("ARCHITECT_TIMEOUT", "20"))
    architect_retries: int = int(os.getenv("ARCHITECT_RETRIES", "2"))
    architect_backoff: float = float(os.getenv("ARCHITECT_BACKOFF", "0.5"))


settings = Settings()