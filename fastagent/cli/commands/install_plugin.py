from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fastagent.plugins.registry import DEFAULT_REGISTRY, install_registry_plugin, load_registry
from fastagent.plugins.manifest import SANDBOX_PROFILE_OPTIONS
from fastagent.utils.project import ensure_project

console = Console()


def install_plugin(
    plugin_name: str = typer.Argument(..., help="Plugin name from registry."),
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
    registry: str = typer.Option(DEFAULT_REGISTRY, "--registry", help="Registry URL or local JSON path."),
    timeout: float = typer.Option(20.0, "--timeout", help="Network timeout in seconds."),
    enable: bool = typer.Option(True, "--enable/--disable", help="Enable plugin in manifest."),
    sandbox_profile: str = typer.Option(
        "",
        "--sandbox-profile",
        help="Optional sandbox profile override (strict | balanced | off).",
    ),
    trust_policy: Path | None = typer.Option(
        None,
        "--trust-policy",
        help="Optional trust policy JSON path. Defaults to <project>/fastagent.trust.json.",
    ),
    allow_unsigned: bool = typer.Option(
        False, "--allow-unsigned", help="Allow install of unsigned plugins (bypass signature requirement)."
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing plugin file if present."),
) -> None:
    try:
        ensure_project(project_path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if timeout <= 0:
        console.print("[red]Error:[/red] --timeout must be > 0")
        raise typer.Exit(code=1)
    profile: str | None = None
    if sandbox_profile.strip():
        profile = sandbox_profile.strip().lower()
        if profile not in SANDBOX_PROFILE_OPTIONS:
            console.print(
                f"[red]Error:[/red] --sandbox-profile must be one of {', '.join(sorted(SANDBOX_PROFILE_OPTIONS))}"
            )
            raise typer.Exit(code=1)

    try:
        registry_data = load_registry(registry=registry, timeout=timeout)
        manifest = install_registry_plugin(
            project_path=project_path,
            registry_data=registry_data,
            plugin_name=plugin_name,
            enable=enable,
            sandbox_profile=profile,
            trust_policy=trust_policy,
            allow_unsigned=allow_unsigned,
            overwrite=overwrite,
            timeout=timeout,
        )
    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    table = Table(title="FastAgent Plugin Installed")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("plugin", plugin_name.strip().lower().replace("-", "_"))
    table.add_row("registry", registry_data.get("name", "unknown"))
    table.add_row("enabled", "yes" if enable else "no")
    normalized_name = plugin_name.strip().lower().replace("-", "_")
    installed = next((item for item in manifest.get("plugins", []) if item.get("name") == normalized_name), {})
    table.add_row("sandbox_profile", str(installed.get("sandbox_profile", profile or "balanced")))
    table.add_row("manifest_plugins_total", str(len(manifest.get("plugins", []))))
    console.print(table)
