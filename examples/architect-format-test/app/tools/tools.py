from importlib import import_module
from pathlib import Path
from typing import Callable


def search_tool(query: str) -> str:
    return f"search results for: {query}"


def calculator_tool(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception:
        return "invalid expression"


def database_query(query: str) -> str:
    return f"database result placeholder for: {query}"


BUILTIN_TOOLS: dict[str, Callable[[str], str]] = {
    "search_tool": search_tool,
    "calculator_tool": calculator_tool,
    "database_query": database_query,
}


def search_tool(input_text: str) -> str:
    return "search_tool output: " + input_text



def _load_external_tools() -> dict[str, Callable[[str], str]]:
    discovered: dict[str, Callable[[str], str]] = {}
    for file in Path(__file__).parent.glob("*_tool.py"):
        module = import_module(f"app.tools.{file.stem}")
        fn = getattr(module, "tool", None)
        if callable(fn):
            discovered[file.stem] = fn
    return discovered


def get_tools() -> dict[str, Callable[[str], str]]:
    tools = dict(BUILTIN_TOOLS)
    tools["search_tool"] = search_tool
    tools.update(_load_external_tools())
    return tools
