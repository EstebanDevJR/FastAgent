from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fastagent.quality.release import run_release_checks, summarize_release_checks, write_release_report

console = Console()


def release_ready(
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Repository root path."),
    run_tests: bool = typer.Option(False, "--run-tests", help="Run pytest as part of readiness checks."),
    strict: bool = typer.Option(False, "--strict", help="Fail when warnings exist."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional JSON report path."),
) -> None:
    checks = run_release_checks(project_path=project_path, run_tests=run_tests)
    summary = summarize_release_checks(checks)

    table = Table(title="FastAgent Release Readiness")
    table.add_column("Check", style="cyan")
    table.add_column("Severity")
    table.add_column("Status", style="green")
    table.add_column("Details", style="yellow")
    for item in checks:
        table.add_row(
            item.name,
            item.severity,
            "PASS" if item.passed else "FAIL",
            item.details,
        )
    console.print(table)

    if output_json is not None:
        write_release_report(output_json, summary)
        console.print(f"[green]Release report written:[/green] {output_json}")

    if not summary["ok"]:
        raise typer.Exit(code=2)
    if strict and summary["warnings"]:
        raise typer.Exit(code=3)
