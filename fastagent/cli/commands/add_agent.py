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


def add_agent(
    agent_name: str = typer.Argument(..., help="Agent class/module name."),
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
) -> None:
    if not NAME_PATTERN.match(agent_name.strip()):
        console.print("[red]Error:[/red] Agent name must start with a letter and use letters, numbers, spaces, '-' or '_'.")
        raise typer.Exit(code=1)

    normalized = _sanitize_name(agent_name)
    if not normalized:
        console.print("[red]Error:[/red] Invalid agent name after normalization.")
        raise typer.Exit(code=1)

    if not (project_path / "app").exists():
        console.print("[red]Error:[/red] This does not look like a FastAgent project (missing app/).")
        raise typer.Exit(code=1)

    agents_dir = project_path / "app" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    agent_file = agents_dir / f"{normalized}_agent.py"

    if agent_file.exists():
        console.print(f"[red]Error:[/red] Agent file already exists: {agent_file}")
        raise typer.Exit(code=1)

    class_name = "".join(part.capitalize() for part in normalized.split("_")) + "Agent"
    content = f'''class {class_name}:
    def run(self, message: str) -> str:
        return f"[{class_name}] {{message}}"
'''
    agent_file.write_text(content, encoding="utf-8")
    console.print(f"[green]Agent created:[/green] {agent_file}")