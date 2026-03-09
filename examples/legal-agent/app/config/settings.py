from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "legal-agent")
    environment: str = os.getenv("ENVIRONMENT", "development")
    agent_type: str = os.getenv("AGENT_TYPE", "chat")
    llm_provider: str = os.getenv("LLM_PROVIDER", "OpenAI")
    vector_db: str = os.getenv("VECTOR_DB", "Qdrant")
    memory_type: str = os.getenv("MEMORY_TYPE", "conversation")
    tracing_backend: str = os.getenv("TRACING_BACKEND", "LangSmith")
    evaluation_enabled: bool = os.getenv("EVALUATION_ENABLED", "true").lower() == "true"


settings = Settings()
