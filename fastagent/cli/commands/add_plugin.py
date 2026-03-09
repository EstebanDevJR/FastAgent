from pathlib import Path
import re
import shutil

import typer
from rich.console import Console

from fastagent.plugins.manifest import upsert_plugin
from fastagent.utils.project import ensure_project, plugin_manifest_path

console = Console()
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*$")


def _sanitize_name(name: str) -> str:
    return name.strip().lower().replace("-", "_")


def add_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name."),
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
    source: str = typer.Option("local", "--source", help="Plugin source (local path, URL, or label)."),
    module: str = typer.Option("", "--module", help="Python module path for the plugin."),
    description: str = typer.Option("", "--description", help="Plugin description."),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="Enable plugin by default."),
    copy_from: Path | None = typer.Option(None, "--copy-from", help="Copy local plugin file/folder into project/plugins."),
) -> None:
    try:
        ensure_project(project_path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    raw_name = plugin_name.strip()
    if not NAME_PATTERN.match(raw_name):
        console.print("[red]Error:[/red] Plugin name must start with a letter and contain only letters, numbers, '-' or '_'.")
        raise typer.Exit(code=1)

    normalized = _sanitize_name(raw_name)
    plugins_dir = project_path / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    if copy_from is not None:
        if not copy_from.exists():
            console.print(f"[red]Error:[/red] --copy-from path not found: {copy_from}")
            raise typer.Exit(code=1)

        target = plugins_dir / copy_from.name
        if copy_from.is_dir():
            if target.exists():
                console.print(f"[red]Error:[/red] Target already exists: {target}")
                raise typer.Exit(code=1)
            shutil.copytree(copy_from, target)
        else:
            shutil.copy2(copy_from, target)

    plugin_record = {
        "name": normalized,
        "source": source,
        "module": module or f"plugins.{normalized}",
        "enabled": enabled,
        "description": description,
    }

    manifest = upsert_plugin(plugin_manifest_path(project_path), plugin_record)
    console.print(f"[green]Plugin upserted:[/green] {normalized} ({len(manifest.get('plugins', []))} total)")
