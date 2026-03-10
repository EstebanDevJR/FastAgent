from pathlib import Path
import json

import typer
from rich.console import Console
from rich.table import Table

from fastagent.plugins.audit import DEFAULT_AUDIT_SECRET, verify_audit_log

console = Console()


def verify_audit(
    log_file: Path = typer.Option(Path("logs/plugin_audit.jsonl"), "--log-file", help="Plugin audit JSONL file."),
    secret: str = typer.Option(DEFAULT_AUDIT_SECRET, "--secret", help="HMAC secret for signature verification."),
    strict_schema: bool = typer.Option(False, "--strict-schema", help="Require mandatory audit event fields."),
    allow_missing: bool = typer.Option(False, "--allow-missing", help="Exit 0 if log file does not exist."),
    max_issues: int = typer.Option(10, "--max-issues", help="Max invalid lines to display."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional JSON report output path."),
) -> None:
    if max_issues < 0:
        console.print("[red]Error:[/red] --max-issues must be >= 0")
        raise typer.Exit(code=1)

    if not log_file.exists():
        if allow_missing:
            console.print(f"[yellow]Audit log not found (allowed):[/yellow] {log_file}")
            if output_json is not None:
                report = {"total": 0, "valid": 0, "invalid": 0, "issues": [], "missing_allowed": True}
                output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return
        console.print(f"[red]Error:[/red] Audit log not found: {log_file}")
        raise typer.Exit(code=1)

    summary = verify_audit_log(log_file=log_file, secret=secret, strict_schema=strict_schema)

    table = Table(title="FastAgent Audit Verification")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("log_file", str(log_file))
    table.add_row("total", str(summary.total))
    table.add_row("valid", str(summary.valid))
    table.add_row("invalid", str(summary.invalid))
    table.add_row("status", "PASS" if summary.invalid == 0 else "FAIL")
    console.print(table)

    if summary.issues and max_issues != 0:
        issues_table = Table(title="Invalid Audit Events")
        issues_table.add_column("Line", style="cyan")
        issues_table.add_column("Reason", style="red")
        for issue in summary.issues[:max_issues]:
            issues_table.add_row(str(issue.line), issue.reason)
        console.print(issues_table)

    if output_json is not None:
        report = {
            "log_file": str(log_file),
            "total": summary.total,
            "valid": summary.valid,
            "invalid": summary.invalid,
            "issues": [{"line": issue.line, "reason": issue.reason} for issue in summary.issues],
        }
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"[green]Report written:[/green] {output_json}")

    if summary.invalid > 0:
        raise typer.Exit(code=2)
