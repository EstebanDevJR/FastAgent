from pathlib import Path
import json

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.approval import load_approval_state, resolve_request, save_approval_state

console = Console()


def approval_resolve(
    request_id: str = typer.Option(..., "--request-id", help="Approval request ID."),
    decision: str = typer.Option(..., "--decision", help="approve | reject"),
    approver: str = typer.Option("manual-approver", "--approver", help="Approver identifier."),
    notes: str = typer.Option("", "--notes", help="Optional approval notes."),
    state_file: Path = typer.Option(Path("rollout.approvals.json"), "--state-file", help="Approval state file."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional output report path."),
) -> None:
    try:
        state = load_approval_state(state_file)
        request = resolve_request(
            state=state,
            request_id=request_id,
            decision=decision,
            approver=approver,
            notes=notes,
        )
        save_approval_state(state_file, state)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    table = Table(title="FastAgent Approval Resolve")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("request_id", str(request.get("id", "")))
    table.add_row("status", str(request.get("status", "")))
    table.add_row("approver", str(request.get("approver", "")))
    table.add_row("deployment_id", str(request.get("deployment_id", "")))
    table.add_row("environment", str(request.get("environment", "")))
    table.add_row("reason", str(request.get("reason", "")))
    console.print(table)

    if output_json is not None:
        output_json.write_text(json.dumps(request, indent=2), encoding="utf-8")
        console.print(f"[green]Approval report written:[/green] {output_json}")
