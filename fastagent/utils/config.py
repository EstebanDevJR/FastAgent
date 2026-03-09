from dataclasses import dataclass
import re


BUILD_TYPE_OPTIONS = [
    "AI Chat Agent",
    "RAG Agent",
    "Multi-Agent System",
    "Tool-Using Agent",
    "Custom",
]

BUILD_TYPE_MAP = {
    "AI Chat Agent": "chat",
    "RAG Agent": "rag",
    "Multi-Agent System": "multi-agent",
    "Tool-Using Agent": "tool-agent",
    "Custom": "custom",
}

PROJECT_TYPE_OPTIONS = ["chat", "rag", "multi-agent", "tool-agent", "custom"]
ARCHITECT_PROVIDER_OPTIONS = ["local", "openai", "ollama"]
ARCHITECT_OPENAI_MODE_OPTIONS = ["auto", "responses", "chat"]

LLM_PROVIDER_OPTIONS = ["OpenAI", "Anthropic", "Google DeepMind", "Meta AI"]
VECTOR_DB_OPTIONS = ["None", "FAISS", "Pinecone", "Qdrant", "Weaviate"]
MEMORY_OPTIONS = ["conversation", "vector", "hybrid"]
TRACING_OPTIONS = ["LangSmith", "OpenTelemetry", "Prometheus", "None"]


def slugify_project_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower())
    slug = slug.replace("_", "-")
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug


@dataclass
class ProjectConfig:
    project_name: str
    project_type: str = "chat"
    description: str = ""
    llm_provider: str = "OpenAI"
    vector_db: str = "None"
    tools: list[str] | None = None
    memory_type: str = "conversation"
    evaluation_enabled: bool = False
    tracing: str = "OpenTelemetry"
    suggested_models: list[str] | None = None
    architect_provider: str = "local"
    architect_model: str = "heuristic"
    architect_openai_mode: str = "auto"
    architect_cache_enabled: bool = True
    architect_cache_ttl_seconds: int = 3600
    architect_notes: list[str] | None = None

    @property
    def project_slug(self) -> str:
        return slugify_project_name(self.project_name)

    @property
    def package_name(self) -> str:
        return self.project_slug.replace("-", "_")

    def normalized_tools(self) -> list[str]:
        base = self.tools or []
        normalized = [tool.strip().replace("-", "_") for tool in base if tool and tool.strip()]
        unique: list[str] = []
        seen = set()
        for tool in normalized:
            if tool not in seen:
                unique.append(tool)
                seen.add(tool)
        return unique

    def to_template_context(self) -> dict:
        return {
            "project_name": self.project_name,
            "project_slug": self.project_slug,
            "package_name": self.package_name,
            "project_type": self.project_type,
            "description": self.description,
            "llm_provider": self.llm_provider,
            "vector_db": self.vector_db,
            "tools": self.normalized_tools(),
            "memory_type": self.memory_type,
            "evaluation_enabled": self.evaluation_enabled,
            "tracing": self.tracing,
            "suggested_models": self.suggested_models or ["Llama 3", "Mistral", "Phi"],
            "tool_list_literal": ", ".join([f'"{t}"' for t in self.normalized_tools()]),
            "evaluation_enabled_literal": "true" if self.evaluation_enabled else "false",
            "architect_provider": self.architect_provider,
            "architect_model": self.architect_model,
            "architect_openai_mode": self.architect_openai_mode,
            "architect_cache_enabled_literal": "true" if self.architect_cache_enabled else "false",
            "architect_cache_ttl_seconds": self.architect_cache_ttl_seconds,
            "architect_notes": self.architect_notes or [],
        }
