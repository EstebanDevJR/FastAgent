from app.config.settings import settings
from app.agents.main_agent import MainAgent
from app.evaluation.evaluator import evaluate_response
from app.observability.tracing import trace_event
from app.policy.engine import PolicyEngine
from app.plugins.policy import get_plugin_policy


class AgentService:
    def __init__(self) -> None:
        self.agent = MainAgent()
        self.policy = PolicyEngine(enabled=settings.policy_enabled, policy_file=settings.policy_file)

    def chat(self, message: str, session_id: str | None = None) -> str:
        sid = session_id or "default"
        plugin_policy = get_plugin_policy()
        token = plugin_policy.start_request()
        trace_event("chat_request", {"message": message, "session_id": sid})

        try:
            decision = self.policy.evaluate(message=message, session_id=sid)
            if not decision.allowed:
                trace_event(
                    "policy_blocked",
                    {
                        "message": message,
                        "session_id": sid,
                        "reason": decision.reason,
                        "rule": decision.matched_rule,
                    },
                )
                return f"blocked_by_policy: {decision.reason} ({decision.matched_rule})"

            response = self.agent.run(message, sid)
            trace_event("chat_response", {"message": message, "response": response, "session_id": sid})
            return response
        finally:
            plugin_policy.end_request(token)

    def check_policy(self, message: str, session_id: str | None = None) -> dict:
        decision = self.policy.evaluate(message=message, session_id=session_id)
        return {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "rule": decision.matched_rule,
        }

    def policy_info(self) -> dict:
        return {
            "enabled": settings.policy_enabled,
            "rule_count": self.policy.rule_count,
            "policy_file": settings.policy_file,
            "load_error": self.policy.load_error,
        }

    def evaluate(self, expected: str, predicted: str) -> dict:
        return evaluate_response(expected=expected, predicted=predicted)

    def cost_status(self, session_id: str | None = None) -> dict:
        return self.agent.cost_status(session_id=session_id)
