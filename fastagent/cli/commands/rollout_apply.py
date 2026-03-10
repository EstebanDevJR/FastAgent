from pathlib import Path
import json

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.traffic import (
    TrafficApplyPlan,
    build_argo_command,
    build_gateway_patch,
    build_gateway_patch_command,
    execute_command,
    load_rollout_decision_report,
    target_weight_from_report,
)

console = Console()

PROVIDER_OPTIONS = {"argo", "gateway"}


def rollout_apply(
    decision_report: Path = typer.Option(..., "--decision-report", help="Rollout controller JSON report."),
    provider: str = typer.Option("argo", "--provider", help="argo | gateway"),
    resource: str = typer.Option("", "--resource", help="Rollout name (argo) or HTTPRoute name (gateway)."),
    namespace: str = typer.Option("default", "--namespace", help="Kubernetes namespace."),
    baseline_backend: str = typer.Option("baseline-svc", "--baseline-backend", help="Gateway baseline backend service name."),
    candidate_backend: str = typer.Option("candidate-svc", "--candidate-backend", help="Gateway candidate backend service name."),
    kubectl_bin: str = typer.Option("kubectl", "--kubectl-bin", help="kubectl binary path."),
    kube_context: str = typer.Option("", "--kube-context", help="Optional kube context."),
    execute: bool = typer.Option(False, "--execute", help="Actually apply change (default is dry-run)."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional output plan report."),
) -> None:
    normalized_provider = provider.strip().lower()
    if normalized_provider not in PROVIDER_OPTIONS:
        console.print(f"[red]Error:[/red] --provider must be one of {', '.join(sorted(PROVIDER_OPTIONS))}")
        raise typer.Exit(code=1)
    if not resource.strip():
        console.print("[red]Error:[/red] --resource is required")
        raise typer.Exit(code=1)

    try:
        report = load_rollout_decision_report(decision_report)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    action, current_phase, target_weight = target_weight_from_report(report)
    plan = TrafficApplyPlan(
        action=action,
        current_phase=current_phase,
        target_weight=target_weight,
        provider=normalized_provider,
        resource=resource.strip(),
        namespace=namespace.strip() or "default",
    )

    if normalized_provider == "argo":
        plan.command = build_argo_command(
            rollout_name=plan.resource,
            weight=plan.target_weight,
            namespace=plan.namespace,
            kubectl_bin=kubectl_bin,
            kube_context=kube_context,
        )
    else:
        patch = build_gateway_patch(
            baseline_backend=baseline_backend.strip(),
            candidate_backend=candidate_backend.strip(),
            candidate_weight=plan.target_weight,
        )
        plan.patch = patch
        plan.command = build_gateway_patch_command(
            route_name=plan.resource,
            namespace=plan.namespace,
            patch=patch,
            kubectl_bin=kubectl_bin,
            kube_context=kube_context,
        )

    table = Table(title="FastAgent Rollout Apply")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("provider", plan.provider)
    table.add_row("resource", plan.resource)
    table.add_row("namespace", plan.namespace)
    table.add_row("action", plan.action)
    table.add_row("current_phase", str(plan.current_phase))
    table.add_row("target_weight", str(plan.target_weight))
    table.add_row("mode", "execute" if execute else "dry-run")
    table.add_row("command", " ".join(plan.command or []))
    console.print(table)

    report_payload = {
        "plan": plan.to_dict(),
        "executed": False,
        "status_code": 0,
        "stdout": "",
        "stderr": "",
    }

    if execute:
        if not plan.command:
            console.print("[red]Error:[/red] Internal error: no command generated")
            raise typer.Exit(code=1)
        status, stdout, stderr = execute_command(plan.command)
        report_payload["executed"] = True
        report_payload["status_code"] = status
        report_payload["stdout"] = stdout
        report_payload["stderr"] = stderr
        if status != 0:
            console.print(f"[red]kubectl command failed:[/red] {stderr or stdout or 'unknown error'}")
            if output_json is not None:
                output_json.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
                console.print(f"[green]Rollout apply report written:[/green] {output_json}")
            raise typer.Exit(code=2)

    if output_json is not None:
        output_json.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        console.print(f"[green]Rollout apply report written:[/green] {output_json}")
