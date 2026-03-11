from app.plugins.policy import PluginExecutionPolicy


def test_plugin_policy_allowlist() -> None:
    policy = PluginExecutionPolicy(
        enabled=True,
        allowed=["safe_plugin"],
        denied=[],
        max_calls_per_request=2,
        failure_threshold=2,
        cooldown_seconds=5,
    )

    token = policy.start_request()
    try:
        allow = policy.can_execute("safe_plugin")
        deny = policy.can_execute("other_plugin")
    finally:
        policy.end_request(token)

    assert allow.allowed is True
    assert deny.allowed is False
    assert deny.reason == "not_in_allowlist"


def test_plugin_policy_circuit_open_after_failures() -> None:
    policy = PluginExecutionPolicy(
        enabled=True,
        allowed=[],
        denied=[],
        max_calls_per_request=3,
        failure_threshold=2,
        cooldown_seconds=60,
    )

    token = policy.start_request()
    try:
        assert policy.can_execute("flaky").allowed is True
        policy.register_call()
        policy.register_failure("flaky")

        assert policy.can_execute("flaky").allowed is True
        policy.register_call()
        policy.register_failure("flaky")

        blocked = policy.can_execute("flaky")
    finally:
        policy.end_request(token)

    assert blocked.allowed is False
    assert blocked.reason == "circuit_open"
