from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fastagent.plugins.signing import generate_keypair

console = Console()


def generate_signing_key(
    output_dir: Path = typer.Option(Path.cwd(), "--output-dir", help="Directory for generated key files."),
    name: str = typer.Option("fastagent_plugin_signing", "--name", help="Base key filename."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite key files if they exist."),
) -> None:
    normalized = name.strip().replace(" ", "_")
    if not normalized:
        console.print("[red]Error:[/red] --name cannot be empty")
        raise typer.Exit(code=1)

    private_key_path = output_dir / f"{normalized}.private.pem"
    public_key_path = output_dir / f"{normalized}.public.pem"

    try:
        result = generate_keypair(private_key_path, public_key_path, overwrite=overwrite)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    table = Table(title="FastAgent Signing Key Generated")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("private_key", result["private_key_path"])
    table.add_row("public_key", result["public_key_path"])
    table.add_row("public_key_base64", result["public_key_base64"])
    console.print(table)
