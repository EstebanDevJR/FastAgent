from app.services.agent_service import AgentService


def test_agent_service_chat() -> None:
    service = AgentService()
    output = service.chat("hello")
    assert isinstance(output, str)


def test_agent_service_eval() -> None:
    service = AgentService()
    result = service.evaluate("hello", "hello world")
    assert result["accuracy"] >= 0
