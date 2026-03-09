from pathlib import Path
import re

import typer
from rich.console import Console

console = Console()
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_\- ]*$")


def _sanitize_name(name: str) -> str:
    normalized = name.strip().lower().replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized


def add_tool(
    tool_name: str = typer.Argument(..., help="Tool name."),
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
    description: str = typer.Option("Custom tool", "--description", help="Tool description."),
) -> None:
    if not NAME_PATTERN.match(tool_name.strip()):
        console.print("[red]Error:[/red] Tool name must start with a letter and use letters, numbers, spaces, '-' or '_'.")
        raise typer.Exit(code=1)

    normalized = _sanitize_name(tool_name)
    if not normalized:
        console.print("[red]Error:[/red] Invalid tool name after normalization.")
        raise typer.Exit(code=1)

    if not (project_path / "app").exists():
        console.print("[red]Error:[/red] This does not look like a FastAgent project (missing app/).")
        raise typer.Exit(code=1)

    tools_dir = project_path / "app" / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)
    tool_file = tools_dir / f"{normalized}_tool.py"

    if tool_file.exists():
        console.print(f"[red]Error:[/red] Tool file already exists: {tool_file}")
        raise typer.Exit(code=1)

    content = f'''"""{description}."""


def tool(input_text: str) -> str:
    return f"{normalized} received: {{input_text}}"
'''
    tool_file.write_text(content, encoding="utf-8")
    console.print(f"[green]Tool created:[/green] {tool_file}")