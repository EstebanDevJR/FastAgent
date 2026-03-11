from app.models.cost_guard import CostGuard


def test_cost_guard_blocks_when_budget_exceeded() -> None:
    guard = CostGuard(
        enabled=True,
        cost_per_1k_tokens_usd=1.0,
        session_budget_usd=0.001,
        global_budget_usd=1.0,
        block_on_budget=True,
    )
    est = guard.estimate_cost(prompt="x" * 4000, history=[])
    decision = guard.can_spend("s1", est)
    assert decision.allowed is False
    assert decision.reason == "session_budget_exceeded"


def test_cost_guard_register_and_status() -> None:
    guard = CostGuard(
        enabled=True,
        cost_per_1k_tokens_usd=0.1,
        session_budget_usd=1.0,
        global_budget_usd=5.0,
        block_on_budget=True,
    )
    guard.register_spend("s1", 0.2)
    status = guard.status("s1")
    assert status["session_spend_usd"] == 0.2
    assert status["global_spend_usd"] == 0.2
