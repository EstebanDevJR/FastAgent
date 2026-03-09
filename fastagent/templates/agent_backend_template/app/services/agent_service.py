from app.agents.main_agent import MainAgent
from app.evaluation.evaluator import evaluate_response


class AgentService:
    def __init__(self) -> None:
        self.agent = MainAgent()

    def chat(self, message: str, session_id: str | None = None) -> str:
        return self.agent.run(message, session_id)

    def evaluate(self, expected: str, predicted: str) -> dict:
        return evaluate_response(expected=expected, predicted=predicted)
