from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def test_create_rejects_invalid_type() -> None:
    result = runner.invoke(app, ["create", "demo", "--type", "invalid", "--yes"])
    assert result.exit_code != 0
    assert "--type must be one of" in result.stdout


def test_create_rejects_invalid_project_name() -> None:
    result = runner.invoke(app, ["create", "!!!", "--yes"])
    assert result.exit_code != 0
    assert "project name must include" in result.stdout


def test_run_detach_requires_docker() -> None:
    result = runner.invoke(app, ["run", "--detach"])
    assert result.exit_code != 0
    assert "--detach can only be used with --docker" in result.stdout


def test_create_rejects_invalid_openai_mode() -> None:
    result = runner.invoke(app, ["create", "demo", "--yes", "--architect-openai-mode", "wrong"])
    assert result.exit_code != 0
    assert "--architect-openai-mode must be one of" in result.stdout


def test_new_commands_help() -> None:
    assert runner.invoke(app, ["doctor", "--help"]).exit_code == 0
    assert runner.invoke(app, ["bench", "--help"]).exit_code == 0
    assert runner.invoke(app, ["canary-check", "--help"]).exit_code == 0
    assert runner.invoke(app, ["canary-shadow", "--help"]).exit_code == 0
    assert runner.invoke(app, ["init-ci", "--help"]).exit_code == 0
    assert runner.invoke(app, ["plugins", "--help"]).exit_code == 0
    assert runner.invoke(app, ["install-plugin", "--help"]).exit_code == 0
    assert runner.invoke(app, ["init-trust", "--help"]).exit_code == 0
    assert runner.invoke(app, ["generate-signing-key", "--help"]).exit_code == 0
    assert runner.invoke(app, ["sign-plugin", "--help"]).exit_code == 0
    assert runner.invoke(app, ["redteam", "--help"]).exit_code == 0
    assert runner.invoke(app, ["release-ready", "--help"]).exit_code == 0
    assert runner.invoke(app, ["trace-replay", "--help"]).exit_code == 0
    assert runner.invoke(app, ["validate-artifacts", "--help"]).exit_code == 0
    assert runner.invoke(app, ["verify-audit", "--help"]).exit_code == 0
    assert runner.invoke(app, ["rollback-webhook", "--help"]).exit_code == 0
    assert runner.invoke(app, ["rollout-controller", "--help"]).exit_code == 0
    assert runner.invoke(app, ["rollout-apply", "--help"]).exit_code == 0
    assert runner.invoke(app, ["autopilot", "--help"]).exit_code == 0
    assert runner.invoke(app, ["approval-list", "--help"]).exit_code == 0
    assert runner.invoke(app, ["approval-resolve", "--help"]).exit_code == 0
