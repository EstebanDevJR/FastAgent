from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fastagent.plugins.manifest import load_manifest, set_plugin_enabled
from fastagent.utils.project import ensure_project, plugin_manifest_path

console = Console()


def list_plugins(
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
) -> None:
    try:
        ensure_project(project_path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    manifest_path = plugin_manifest_path(project_path)
    manifest = load_manifest(manifest_path)
    plugins = manifest.get("plugins", [])

    if not plugins:
        console.print("[yellow]No plugins configured.[/yellow]")
        return

    table = Table(title="FastAgent Plugins")
    table.add_column("Name", style="cyan")
    table.add_column("Enabled")
    table.add_column("Module", style="green")
    table.add_column("Source", style="green")

    for item in plugins:
        enabled = "yes" if item.get("enabled", True) else "no"
        color = "green" if enabled == "yes" else "yellow"
        table.add_row(
            item.get("name", ""),
            f"[{color}]{enabled}[/{color}]",
            item.get("module", ""),
            item.get("source", ""),
        )

    console.print(table)


def enable_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name."),
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
) -> None:
    try:
        ensure_project(project_path)
        set_plugin_enabled(plugin_manifest_path(project_path), plugin_name, True)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    console.print(f"[green]Plugin enabled:[/green] {plugin_name}")


def disable_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name."),
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
) -> None:
    try:
        ensure_project(project_path)
        set_plugin_enabled(plugin_manifest_path(project_path), plugin_name, False)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    console.print(f"[green]Plugin disabled:[/green] {plugin_name}")
