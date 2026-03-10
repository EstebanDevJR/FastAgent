from pathlib import Path
import json
import os

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.webhook import build_rollback_payload, post_rollback_webhook, sign_payload

console = Console()


def rollback_webhook(
    url: str = typer.Option("", "--url", help="Rollback webhook URL. Falls back to FASTAGENT_ROLLBACK_WEBHOOK_URL."),
    secret: str = typer.Option(
        "",
        "--secret",
        help="Webhook secret. Falls back to FASTAGENT_ROLLBACK_WEBHOOK_SECRET.",
    ),
    deployment_id: str = typer.Option("unknown", "--deployment-id", help="Deployment identifier."),
    reason: str = typer.Option("canary_failure", "--reason", help="Rollback reason."),
    metadata_json: Path | None = typer.Option(None, "--metadata-json", help="Optional metadata JSON file."),
    canary_report: Path | None = typer.Option(None, "--canary-report", help="Optional canary report JSON file."),
    timeout: float = typer.Option(15.0, "--timeout", help="Webhook timeout in seconds."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Build and sign payload without sending."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional output payload report."),
) -> None:
    resolved_url = url.strip() or os.getenv("FASTAGENT_ROLLBACK_WEBHOOK_URL", "").strip()
    resolved_secret = secret.strip() or os.getenv("FASTAGENT_ROLLBACK_WEBHOOK_SECRET", "").strip()

    if timeout <= 0:
        console.print("[red]Error:[/red] --timeout must be > 0")
        raise typer.Exit(code=1)
    if not resolved_url:
        console.print("[red]Error:[/red] rollback webhook URL is required.")
        raise typer.Exit(code=1)
    if not resolved_secret:
        console.print("[red]Error:[/red] rollback webhook secret is required.")
        raise typer.Exit(code=1)

    metadata: dict = {}
    if metadata_json is not None:
        try:
            metadata = _load_json_dict(metadata_json, label="metadata")
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)

    canary: dict = {}
    if canary_report is not None:
        try:
            canary = _load_json_dict(canary_report, label="canary report")
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)

    payload = build_rollback_payload(
        deployment_id=deployment_id,
        reason=reason,
        metadata=metadata,
        canary_report=canary,
    )
    signature = sign_payload(payload, secret=resolved_secret)

    table = Table(title="FastAgent Rollback Webhook")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("url", resolved_url)
    table.add_row("deployment_id", deployment_id)
    table.add_row("reason", reason)
    table.add_row("dry_run", "yes" if dry_run else "no")
    table.add_row("signature_prefix", signature[:16])
    console.print(table)

    report = {
        "url": resolved_url,
        "deployment_id": deployment_id,
        "reason": reason,
        "dry_run": dry_run,
        "signature": signature,
        "payload": payload,
    }

    if dry_run:
        if output_json is not None:
            output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
            console.print(f"[green]Webhook dry-run report written:[/green] {output_json}")
        return

    try:
        status_code, response_text = post_rollback_webhook(
            url=resolved_url,
            payload=payload,
            secret=resolved_secret,
            timeout=timeout,
        )
    except (RuntimeError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    report["status_code"] = status_code
    report["response"] = response_text
    console.print(f"[cyan]Webhook response:[/cyan] status={status_code}")

    if output_json is not None:
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"[green]Webhook report written:[/green] {output_json}")

    if status_code >= 400:
        raise typer.Exit(code=2)


def _load_json_dict(path: Path, label: str) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{label} file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} JSON must be an object")
    return payload
