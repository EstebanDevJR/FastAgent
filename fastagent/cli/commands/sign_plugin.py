from pathlib import Path
import json

import typer
from rich.console import Console

from fastagent.plugins.manifest import SANDBOX_PROFILE_OPTIONS
from fastagent.plugins.signing import load_private_key, public_key_to_base64, sha256_hex, sign_payload

console = Console()


def sign_plugin(
    plugin_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, help="Plugin .py file to sign."),
    private_key: Path = typer.Option(..., "--private-key", exists=True, file_okay=True, dir_okay=False, help="Ed25519 private key PEM."),
    key_id: str = typer.Option(..., "--key-id", help="Signing key id used in registry."),
    source: str = typer.Option("", "--source", help="Source URL/path for registry entry (defaults to plugin file path)."),
    module: str = typer.Option("", "--module", help="Python module path (defaults to plugins.<name>)."),
    name: str = typer.Option("", "--name", help="Plugin name (defaults to file stem)."),
    description: str = typer.Option("", "--description", help="Plugin description."),
    filename: str = typer.Option("", "--filename", help="Target filename in project/plugins."),
    sandbox_profile: str = typer.Option("balanced", "--sandbox-profile", help="strict | balanced | off"),
    include_key: bool = typer.Option(False, "--include-key", help="Include key block in output."),
    output: Path | None = typer.Option(None, "--output", help="Optional output JSON file."),
) -> None:
    plugin_name = (name.strip().lower().replace("-", "_") if name.strip() else plugin_file.stem.lower().replace("-", "_"))
    if not plugin_name:
        console.print("[red]Error:[/red] Could not infer plugin name.")
        raise typer.Exit(code=1)

    key_id_value = key_id.strip()
    if not key_id_value:
        console.print("[red]Error:[/red] --key-id cannot be empty")
        raise typer.Exit(code=1)
    profile = sandbox_profile.strip().lower()
    if profile not in SANDBOX_PROFILE_OPTIONS:
        console.print(
            f"[red]Error:[/red] --sandbox-profile must be one of {', '.join(sorted(SANDBOX_PROFILE_OPTIONS))}."
        )
        raise typer.Exit(code=1)

    payload = plugin_file.read_bytes()
    digest = sha256_hex(payload)

    try:
        private = load_private_key(private_key)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    signature = sign_payload(payload, private)
    public_key_b64 = public_key_to_base64(private.public_key())

    plugin_entry = {
        "name": plugin_name,
        "description": description.strip(),
        "source": source.strip() or str(plugin_file),
        "module": module.strip() or f"plugins.{plugin_name}",
        "filename": filename.strip() or plugin_file.name,
        "sandbox_profile": profile,
        "sha256": digest,
        "signing_key": key_id_value,
        "signature": signature,
    }

    result: dict = {"plugin": plugin_entry}
    if include_key:
        result["key"] = {
            "id": key_id_value,
            "algorithm": "ed25519",
            "public_key": public_key_b64,
        }

    content = json.dumps(result, indent=2) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        console.print(f"[green]Signature bundle written:[/green] {output}")
        return

    console.print(content)
