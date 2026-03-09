from pathlib import Path

import typer
from rich.console import Console

from fastagent.plugins.manifest import remove_plugin
from fastagent.utils.project import ensure_project, plugin_manifest_path

console = Console()


def remove_plugin_cmd(
    plugin_name: str = typer.Argument(..., help="Plugin name."),
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
) -> None:
    try:
        ensure_project(project_path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    manifest = remove_plugin(plugin_manifest_path(project_path), plugin_name.strip().lower().replace("-", "_"))
    console.print(f"[green]Plugin removed (if present).[/green] Remaining: {len(manifest.get('plugins', []))}")
