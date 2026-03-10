from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fastagent.plugins.trust import save_trust_policy
from fastagent.utils.project import ensure_project

console = Console()


def init_trust(
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
    policy_file: str = typer.Option("fastagent.trust.json", "--policy-file", help="Trust policy filename."),
    require_signed: bool = typer.Option(True, "--require-signed/--allow-unsigned-default", help="Require plugin Ed25519 signatures by default."),
    trusted_key_id: list[str] = typer.Option([], "--trusted-key-id", help="Trusted signing key id (repeatable)."),
    trusted_public_key: list[str] = typer.Option([], "--trusted-public-key", help="Trusted public key (base64, repeatable)."),
    allowed_registry: list[str] = typer.Option([], "--allowed-registry", help="Allowed registry name (repeatable)."),
    allow_unsigned_plugin: list[str] = typer.Option([], "--allow-unsigned-plugin", help="Plugin name allowed unsigned (repeatable)."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing trust policy."),
) -> None:
    try:
        ensure_project(project_path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    target = project_path / policy_file
    if target.exists() and not overwrite:
        console.print(f"[red]Error:[/red] Policy file already exists: {target}. Use --overwrite to replace.")
        raise typer.Exit(code=1)

    policy = {
        "require_signed": require_signed,
        "trusted_key_ids": trusted_key_id,
        "trusted_public_keys": trusted_public_key,
        "allowed_registries": allowed_registry,
        "allow_unsigned_plugins": [item.strip().lower().replace("-", "_") for item in allow_unsigned_plugin],
    }
    save_trust_policy(target, policy)

    table = Table(title="FastAgent Trust Policy Initialized")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("policy_file", str(target))
    table.add_row("require_signed", "true" if require_signed else "false")
    table.add_row("trusted_key_ids", str(len(trusted_key_id)))
    table.add_row("trusted_public_keys", str(len(trusted_public_key)))
    table.add_row("allowed_registries", str(len(allowed_registry)))
    table.add_row("allow_unsigned_plugins", str(len(allow_unsigned_plugin)))
    console.print(table)
