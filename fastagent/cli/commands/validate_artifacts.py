from pathlib import Path
import json

import typer
from rich.console import Console
from rich.table import Table

from fastagent.quality.artifacts import SUPPORTED_ARTIFACTS, validate_artifact_file

console = Console()


def validate_artifacts(
    artifact: list[str] = typer.Option(
        [],
        "--artifact",
        help="Artifact descriptor in format type:path. Repeat for multiple files.",
    ),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional JSON report output path."),
) -> None:
    if not artifact:
        console.print("[red]Error:[/red] at least one --artifact type:path is required")
        raise typer.Exit(code=1)

    results = []
    parse_errors: list[str] = []
    for item in artifact:
        if ":" not in item:
            parse_errors.append(f"invalid descriptor '{item}', expected type:path")
            continue
        artifact_type, raw_path = item.split(":", 1)
        artifact_type = artifact_type.strip().lower()
        path = Path(raw_path.strip())
        if artifact_type not in SUPPORTED_ARTIFACTS:
            parse_errors.append(f"unsupported artifact type '{artifact_type}'")
            continue
        results.append(validate_artifact_file(artifact_type, path))

    table = Table(title="FastAgent Artifact Validation")
    table.add_column("Artifact", style="cyan")
    table.add_column("Path")
    table.add_column("Status", style="green")
    table.add_column("Errors", style="yellow")
    for result in results:
        table.add_row(
            result.artifact_type,
            result.path,
            "PASS" if result.valid else "FAIL",
            " | ".join(result.errors) if result.errors else "none",
        )
    for msg in parse_errors:
        table.add_row("parse", "-", "FAIL", msg)
    console.print(table)

    report = {
        "ok": not parse_errors and all(item.valid for item in results),
        "results": [item.to_dict() for item in results],
        "parse_errors": parse_errors,
    }

    if output_json is not None:
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"[green]Validation report written:[/green] {output_json}")

    if not report["ok"]:
        raise typer.Exit(code=2)
