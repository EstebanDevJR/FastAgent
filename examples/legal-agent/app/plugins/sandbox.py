from __future__ import annotations

import base64
from importlib import import_module
import json
import subprocess
import sys
import time

from app.plugins.audit import write_plugin_audit_event


def run_plugin_module(
    module: str,
    input_text: str,
    plugin_name: str | None = None,
    profile: str = "balanced",
    timeout_seconds: float = 2.0,
    memory_mb: int = 256,
    strict_timeout_seconds: float = 1.0,
    strict_memory_mb: int = 128,
    sandbox_enabled: bool = True,
    audit_enabled: bool = True,
    audit_log_path: str = "logs/plugin_audit.jsonl",
    audit_secret: str = "fastagent-dev-audit-secret",
) -> str:
    started = time.perf_counter()
    effective_profile = (profile or "balanced").strip().lower()
    if effective_profile not in {"strict", "balanced", "off"}:
        effective_profile = "balanced"

    effective_timeout = max(0.1, timeout_seconds)
    effective_memory = max(0, memory_mb)
    effective_sandbox = sandbox_enabled

    if effective_profile == "off":
        effective_sandbox = False
    elif effective_profile == "strict":
        effective_timeout = min(effective_timeout, max(0.1, strict_timeout_seconds))
        effective_memory = min(effective_memory, max(32, strict_memory_mb))

    name = plugin_name or module

    if not effective_sandbox:
        result = _run_in_process(module=module, input_text=input_text)
        status = "ok" if not result.startswith("plugin_") else "error"
        _audit(
            plugin_name=name,
            module=module,
            profile=effective_profile,
            sandbox_enabled=effective_sandbox,
            timeout_seconds=effective_timeout,
            memory_mb=effective_memory,
            duration_ms=(time.perf_counter() - started) * 1000,
            status=status,
            input_text=input_text,
            result=result if status == "ok" else "",
            error="" if status == "ok" else result,
            audit_enabled=audit_enabled,
            audit_log_path=audit_log_path,
            audit_secret=audit_secret,
        )
        return result

    encoded = base64.b64encode(input_text.encode("utf-8")).decode("ascii")
    cmd = [
        sys.executable,
        "-m",
        "app.plugins.runner",
        "--module",
        module,
        "--input-base64",
        encoded,
        "--memory-mb",
        str(effective_memory),
    ]

    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired:
        result = f"plugin_timeout:{module}"
        _audit(
            plugin_name=name,
            module=module,
            profile=effective_profile,
            sandbox_enabled=effective_sandbox,
            timeout_seconds=effective_timeout,
            memory_mb=effective_memory,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="timeout",
            input_text=input_text,
            result="",
            error=result,
            audit_enabled=audit_enabled,
            audit_log_path=audit_log_path,
            audit_secret=audit_secret,
        )
        return result
    except Exception as exc:
        result = f"plugin_exec_error:{module}:{exc}"
        _audit(
            plugin_name=name,
            module=module,
            profile=effective_profile,
            sandbox_enabled=effective_sandbox,
            timeout_seconds=effective_timeout,
            memory_mb=effective_memory,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="exec_error",
            input_text=input_text,
            result="",
            error=result,
            audit_enabled=audit_enabled,
            audit_log_path=audit_log_path,
            audit_secret=audit_secret,
        )
        return result

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if completed.returncode != 0:
        result = ""
        error = f"plugin_error:{module}:{stderr or 'runner_failed'}"
        if stdout:
            try:
                payload = json.loads(stdout)
                if isinstance(payload, dict) and payload.get("error"):
                    error = f"plugin_error:{module}:{payload['error']}"
            except json.JSONDecodeError:
                pass
        _audit(
            plugin_name=name,
            module=module,
            profile=effective_profile,
            sandbox_enabled=effective_sandbox,
            timeout_seconds=effective_timeout,
            memory_mb=effective_memory,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="error",
            input_text=input_text,
            result=result,
            error=error,
            audit_enabled=audit_enabled,
            audit_log_path=audit_log_path,
            audit_secret=audit_secret,
        )
        return error

    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        error = f"plugin_error:{module}:invalid_runner_output"
        _audit(
            plugin_name=name,
            module=module,
            profile=effective_profile,
            sandbox_enabled=effective_sandbox,
            timeout_seconds=effective_timeout,
            memory_mb=effective_memory,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="error",
            input_text=input_text,
            result="",
            error=error,
            audit_enabled=audit_enabled,
            audit_log_path=audit_log_path,
            audit_secret=audit_secret,
        )
        return error
    if not isinstance(payload, dict) or not payload.get("ok", False):
        error = f"plugin_error:{module}:{payload.get('error', 'unknown') if isinstance(payload, dict) else 'unknown'}"
        _audit(
            plugin_name=name,
            module=module,
            profile=effective_profile,
            sandbox_enabled=effective_sandbox,
            timeout_seconds=effective_timeout,
            memory_mb=effective_memory,
            duration_ms=(time.perf_counter() - started) * 1000,
            status="error",
            input_text=input_text,
            result="",
            error=error,
            audit_enabled=audit_enabled,
            audit_log_path=audit_log_path,
            audit_secret=audit_secret,
        )
        return error
    result = str(payload.get("result", ""))
    _audit(
        plugin_name=name,
        module=module,
        profile=effective_profile,
        sandbox_enabled=effective_sandbox,
        timeout_seconds=effective_timeout,
        memory_mb=effective_memory,
        duration_ms=(time.perf_counter() - started) * 1000,
        status="ok",
        input_text=input_text,
        result=result,
        error="",
        audit_enabled=audit_enabled,
        audit_log_path=audit_log_path,
        audit_secret=audit_secret,
    )
    return result


def _run_in_process(module: str, input_text: str) -> str:
    try:
        target = import_module(module)
        fn = getattr(target, "tool", None)
        if not callable(fn):
            return f"plugin_error:{module}:missing_tool_function"
        result = fn(input_text)
        return str(result)
    except Exception as exc:
        return f"plugin_error:{module}:{exc}"


def _audit(
    *,
    plugin_name: str,
    module: str,
    profile: str,
    sandbox_enabled: bool,
    timeout_seconds: float,
    memory_mb: int,
    duration_ms: float,
    status: str,
    input_text: str,
    result: str,
    error: str,
    audit_enabled: bool,
    audit_log_path: str,
    audit_secret: str,
) -> None:
    try:
        write_plugin_audit_event(
            plugin_name=plugin_name,
            module=module,
            profile=profile,
            sandbox_enabled=sandbox_enabled,
            timeout_seconds=timeout_seconds,
            memory_mb=memory_mb,
            duration_ms=duration_ms,
            status=status,
            input_text=input_text,
            result=result,
            error=error,
            log_path=audit_log_path,
            secret=audit_secret,
            enabled=audit_enabled,
        )
    except Exception:
        return
