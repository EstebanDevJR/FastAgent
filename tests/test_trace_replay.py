from pathlib import Path

from typer.testing import CliRunner

from fastagent.cli.main import app
from fastagent.trace.replay import extract_chat_messages, load_trace_events


runner = CliRunner()


def test_trace_loader_and_message_extraction(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        "# trace\n"
        '{"timestamp":"2026-01-01T00:00:00Z","event":"chat_request","payload":{"message":"hello"}}\n'
        '{"timestamp":"2026-01-01T00:00:01Z","event":"tool_call","payload":{"message":"skip"}}\n'
        '{"timestamp":"2026-01-01T00:00:02Z","event":"chat_request","payload":{"prompt":"how are you"}}\n',
        encoding="utf-8",
    )

    events = load_trace_events(trace)
    messages = extract_chat_messages(events, event_name="chat_request")

    assert len(events) == 3
    assert messages == ["hello", "how are you"]


def test_trace_replay_dry_run(tmp_path: Path) -> None:
    trace = tmp_path / "trace.jsonl"
    trace.write_text(
        '{"event":"chat_request","payload":{"message":"hello"}}\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["trace-replay", "--trace-file", str(trace)])

    assert result.exit_code == 0
    assert "Dry run mode" in result.stdout


def test_trace_replay_invalid_json(tmp_path: Path) -> None:
    trace = tmp_path / "trace_bad.jsonl"
    trace.write_text("{not json}\n", encoding="utf-8")

    result = runner.invoke(app, ["trace-replay", "--trace-file", str(trace)])

    assert result.exit_code != 0
    assert "Invalid JSON on line 1" in result.stdout
