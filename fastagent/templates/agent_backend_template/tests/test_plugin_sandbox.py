from pathlib import Path
import json

from app.plugins.audit import verify_plugin_audit_signature
from app.plugins.sandbox import run_plugin_module


def test_plugin_sandbox_in_process(tmp_path: Path) -> None:
    tools_dir = Path("app/tools")
    tools_dir.mkdir(parents=True, exist_ok=True)
    module_path = tools_dir / "sandbox_tmp_tool.py"
    module_path.write_text(
        "def tool(input_text: str) -> str:\n"
        "    return 'ok:' + input_text\n",
        encoding="utf-8",
    )

    try:
        result = run_plugin_module(
            module="app.tools.sandbox_tmp_tool",
            input_text="hello",
            sandbox_enabled=False,
        )
    finally:
        if module_path.exists():
            module_path.unlink()

    assert result == "ok:hello"


def test_plugin_sandbox_timeout(tmp_path: Path) -> None:
    plugins_dir = Path("plugins")
    plugins_dir.mkdir(parents=True, exist_ok=True)
    module_path = plugins_dir / "timeout_tmp.py"
    module_path.write_text(
        "import time\n"
        "def tool(input_text: str) -> str:\n"
        "    time.sleep(0.5)\n"
        "    return input_text\n",
        encoding="utf-8",
    )

    try:
        result = run_plugin_module(
            module="plugins.timeout_tmp",
            input_text="hello",
            timeout_seconds=0.05,
            sandbox_enabled=True,
        )
    finally:
        if module_path.exists():
            module_path.unlink()

    assert result.startswith("plugin_timeout:")


def test_plugin_audit_signed_event(tmp_path: Path) -> None:
    tools_dir = Path("app/tools")
    tools_dir.mkdir(parents=True, exist_ok=True)
    module_path = tools_dir / "audit_tmp_tool.py"
    module_path.write_text(
        "def tool(input_text: str) -> str:\n"
        "    return 'audited:' + input_text\n",
        encoding="utf-8",
    )
    audit_log = tmp_path / "plugin_audit.jsonl"
    secret = "qa-audit-secret"

    try:
        result = run_plugin_module(
            module="app.tools.audit_tmp_tool",
            input_text="hello",
            plugin_name="audit_tmp_tool",
            profile="balanced",
            sandbox_enabled=False,
            audit_enabled=True,
            audit_log_path=str(audit_log),
            audit_secret=secret,
        )
    finally:
        if module_path.exists():
            module_path.unlink()

    assert result == "audited:hello"
    lines = [line for line in audit_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["plugin"] == "audit_tmp_tool"
    assert event["status"] == "ok"
    assert verify_plugin_audit_signature(event, secret=secret) is True
