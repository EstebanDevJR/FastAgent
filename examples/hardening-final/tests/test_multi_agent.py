from app.agents.orchestrator import MultiAgentOrchestrator
from app.models.llm import LLMClient


def test_multi_agent_orchestrator_success() -> None:
    orchestrator = MultiAgentOrchestrator(llm=LLMClient(), max_retries=1, max_tasks=3)
    result = orchestrator.run("analyze contracts and extract risks")
    assert len(result.plan.tasks) >= 1
    assert result.review.score >= 0
    assert isinstance(result.review.final_answer, str)


class FlakyLLM:
    def __init__(self) -> None:
        self._fail_once_done = False

    def generate(self, prompt: str, context: list[str] | None = None) -> str:
        _ = context
        if prompt.startswith("Execute task_1") and not self._fail_once_done:
            self._fail_once_done = True
            return ""
        return f"ok:{prompt}"


def test_multi_agent_orchestrator_retry_path() -> None:
    orchestrator = MultiAgentOrchestrator(llm=FlakyLLM(), max_retries=2, max_tasks=2)
    result = orchestrator.run("task one and task two")
    assert any(item.attempts > 1 for item in result.workers)
