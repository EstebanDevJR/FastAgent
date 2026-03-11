from app.config.settings import settings
from app.agents.orchestrator import MultiAgentOrchestrator
from app.memory.memory import get_memory
from app.models.llm import LLMClient
from app.rag.retriever import Retriever
from app.tools.tools import get_tools


class MainAgent:
    def __init__(self) -> None:
        self.llm = LLMClient(provider=settings.llm_provider)
        self.memory = get_memory(settings.memory_type)
        self.retriever = Retriever(vector_db=settings.vector_db)
        self.tools = get_tools()
        self.orchestrator = MultiAgentOrchestrator(
            llm=self.llm,
            max_retries=settings.multi_agent_max_retries,
            max_tasks=settings.multi_agent_max_tasks,
        )

    def run(self, message: str, session_id: str | None = None) -> str:
        sid = session_id or "default"
        history = self.memory.recall(sid, query=message)

        if settings.agent_type == "multi-agent":
            return self._run_multi_agent(message, sid, history)
        if settings.agent_type == "tool-agent":
            return self._run_tool_agent(message, sid, history)
        if settings.agent_type == "rag":
            return self._run_rag_agent(message, sid, history)
        return self._run_chat_agent(message, sid, history)

    def _run_chat_agent(self, message: str, session_id: str, history: list[str]) -> str:
        response = self.llm.generate(prompt=message, context=history, session_id=session_id)
        self.memory.store(session_id, f"user: {message}")
        self.memory.store(session_id, f"assistant: {response}")
        return response

    def _run_tool_agent(self, message: str, session_id: str, history: list[str]) -> str:
        tool_output = ""
        if message.startswith("tool:"):
            parts = message.split(":", 2)
            if len(parts) == 3:
                tool_name = parts[1].strip()
                tool_input = parts[2].strip()
                if tool_name in self.tools:
                    tool_output = self.tools[tool_name](tool_input)
        prompt = f"Message: {message}\nTool output: {tool_output}" if tool_output else message
        response = self.llm.generate(prompt=prompt, context=history, session_id=session_id)
        self.memory.store(session_id, f"user: {message}")
        self.memory.store(session_id, f"assistant: {response}")
        return response

    def _run_rag_agent(self, message: str, session_id: str, history: list[str]) -> str:
        docs = self.retriever.retrieve(message)
        prompt = f"Question: {message}\nContext: {' | '.join(docs)}"
        response = self.llm.generate(prompt=prompt, context=history, session_id=session_id)
        self.memory.store(session_id, f"user: {message}")
        self.memory.store(session_id, f"assistant: {response}")
        return response

    def _run_multi_agent(self, message: str, session_id: str, history: list[str]) -> str:
        result = self.orchestrator.run(message=message, history=history)
        response = (
            f"{result.review.final_answer} | approved={result.review.approved} "
            f"| score={result.review.score} | tasks={len(result.plan.tasks)}"
        )
        self.memory.store(session_id, f"user: {message}")
        self.memory.store(session_id, f"assistant: {response}")
        return response

    def cost_status(self, session_id: str | None = None) -> dict:
        return self.llm.cost_status(session_id=session_id)
