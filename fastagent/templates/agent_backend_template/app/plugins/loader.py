from pathlib import Path
import json
from typing import Callable

from app.config.settings import settings
from app.plugins.audit import write_plugin_audit_event
from app.plugins.policy import get_plugin_policy
from app.plugins.sandbox import run_plugin_module


def _manifest_path() -> Path:
    return Path(__file__).resolve().parents[2] / "fastagent.plugins.json"


def load_plugins() -> list[dict]:
    manifest = _manifest_path()
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list):
        return []
    return [item for item in plugins if isinstance(item, dict)]


def enabled_plugins() -> list[dict]:
    return [plugin for plugin in load_plugins() if bool(plugin.get("enabled", True))]


def load_plugin_tools() -> dict[str, Callable[[str], str]]:
    tools: dict[str, Callable[[str], str]] = {}
    for plugin in enabled_plugins():
        name = str(plugin.get("name", "")).strip()
        module = str(plugin.get("module", "")).strip()
        profile = str(plugin.get("sandbox_profile", settings.plugin_profile_default)).strip().lower() or "balanced"
        if not name or not module:
            continue

        def _run(input_text: str, module_name: str = module, plugin_name: str = name, sandbox_profile: str = profile) -> str:
            policy = get_plugin_policy()
            decision = policy.can_execute(plugin_name)
            if not decision.allowed:
                error = f"plugin_blocked:{plugin_name}:{decision.reason}"
                write_plugin_audit_event(
                    plugin_name=plugin_name,
                    module=module_name,
                    profile=sandbox_profile,
                    sandbox_enabled=settings.plugin_sandbox_enabled,
                    timeout_seconds=settings.plugin_timeout_seconds,
                    memory_mb=settings.plugin_memory_mb,
                    duration_ms=0.0,
                    status="blocked",
                    input_text=input_text,
                    result="",
                    error=error,
                    log_path=settings.plugin_audit_log_path,
                    secret=settings.plugin_audit_secret,
                    enabled=settings.plugin_audit_enabled,
                )
                return error

            policy.register_call()
            result = run_plugin_module(
                module=module_name,
                input_text=input_text,
                plugin_name=plugin_name,
                profile=sandbox_profile,
                timeout_seconds=settings.plugin_timeout_seconds,
                memory_mb=settings.plugin_memory_mb,
                strict_timeout_seconds=settings.plugin_strict_timeout_seconds,
                strict_memory_mb=settings.plugin_strict_memory_mb,
                sandbox_enabled=settings.plugin_sandbox_enabled,
                audit_enabled=settings.plugin_audit_enabled,
                audit_log_path=settings.plugin_audit_log_path,
                audit_secret=settings.plugin_audit_secret,
            )
            if result.startswith("plugin_"):
                policy.register_failure(plugin_name)
            else:
                policy.register_success(plugin_name)
            return result

        tools[name] = _run

    return tools
