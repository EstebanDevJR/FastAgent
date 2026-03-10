from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.approval import load_approval_state

console = Console()


def approval_list(
    state_file: Path = typer.Option(Path("rollout.approvals.json"), "--state-file", help="Approval state file."),
    all_requests: bool = typer.Option(False, "--all", help="Include resolved requests."),
    limit: int = typer.Option(25, "--limit", help="Max requests to show."),
) -> None:
    if limit <= 0:
        console.print("[red]Error:[/red] --limit must be > 0")
        raise typer.Exit(code=1)

    try:
        state = load_approval_state(state_file)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    requests = state.get("requests", [])
    if not isinstance(requests, list):
        requests = []

    filtered = [item for item in requests if isinstance(item, dict)]
    if not all_requests:
        filtered = [item for item in filtered if str(item.get("status", "")).strip() == "pending"]
    filtered = list(reversed(filtered))[:limit]

    table = Table(title="FastAgent Approval Requests")
    table.add_column("ID", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Deployment")
    table.add_column("Env")
    table.add_column("Reason")
    table.add_column("Phase")
    table.add_column("Expires")
    table.add_column("Esc")
    table.add_column("Updated")
    if not filtered:
        table.add_row("-", "-", "-", "-", "-", "-", "-", "-", "-")
        console.print(table)
        return

    for req in filtered:
        table.add_row(
            str(req.get("id", "")),
            str(req.get("status", "")),
            str(req.get("deployment_id", "")),
            str(req.get("environment", "")),
            str(req.get("reason", "")),
            f"{req.get('current_phase', '')}->{req.get('next_phase', '')}",
            str(req.get("expires_at", "")),
            str(req.get("escalation_count", 0)),
            str(req.get("updated_at", req.get("created_at", ""))),
        )
    console.print(table)
