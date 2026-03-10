from __future__ import annotations

import argparse
import base64
from importlib import import_module
import json
import sys


def _set_memory_limit(memory_mb: int) -> None:
    if memory_mb <= 0:
        return
    try:
        import resource
    except Exception:
        return

    limit_bytes = int(memory_mb) * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit_bytes, limit_bytes))
    except Exception:
        # Best effort, platform support varies.
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="FastAgent plugin runner")
    parser.add_argument("--module", required=True)
    parser.add_argument("--input-base64", required=True)
    parser.add_argument("--memory-mb", type=int, default=0)
    args = parser.parse_args()

    _set_memory_limit(args.memory_mb)

    try:
        raw = base64.b64decode(args.input_base64.encode("ascii"))
        input_text = raw.decode("utf-8")
        module = import_module(args.module)
        fn = getattr(module, "tool", None)
        if not callable(fn):
            raise ValueError(f"module '{args.module}' does not expose callable tool(input_text)")
        result = fn(input_text)
        if not isinstance(result, str):
            result = str(result)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2

    print(json.dumps({"ok": True, "result": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
