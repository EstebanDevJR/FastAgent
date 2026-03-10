from pathlib import Path
import json
import os

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.rollout import (
    apply_rollout_decision,
    decide_rollout,
    estimate_rollout_risk,
    evaluate_rollout_reports,
    load_rollout_state,
    parse_phase_plan,
    save_rollout_state,
)
from fastagent.deployment.webhook import build_rollback_payload, post_rollback_webhook

console = Console()


def rollout_controller(
    state_file: Path = typer.Option(Path("rollout.state.json"), "--state-file", help="Persistent rollout state file."),
    canary_report: Path | None = typer.Option(None, "--canary-report", help="Canary check JSON report."),
    shadow_report: Path | None = typer.Option(None, "--shadow-report", help="Shadow canary JSON report."),
    phase_plan: str = typer.Option("5,25,50,100", "--phase-plan", help="Comma-separated phase percentages."),
    target_phase: int = typer.Option(100, "--target-phase", help="Target rollout phase percentage."),
    adaptive: bool = typer.Option(True, "--adaptive/--static", help="Enable adaptive phase jumps based on risk."),
    min_phase_increment: int = typer.Option(1, "--min-phase-increment", help="Minimum phase steps per advance."),
    max_phase_increment: int = typer.Option(2, "--max-phase-increment", help="Maximum phase steps per advance."),
    stability_window: int = typer.Option(2, "--stability-window", help="Successful windows needed before acceleration."),
    hold_risk_threshold: float = typer.Option(0.7, "--hold-risk-threshold", help="Risk threshold to hold rollout."),
    deployment_id: str = typer.Option("unknown", "--deployment-id", help="Deployment identifier."),
    rollback_on_fail: bool = typer.Option(True, "--rollback-on-fail/--no-rollback-on-fail", help="Trigger webhook on failed rollout decision."),
    rollback_webhook_url: str = typer.Option(
        "",
        "--rollback-webhook-url",
        help="Rollback webhook URL (falls back to FASTAGENT_ROLLBACK_WEBHOOK_URL).",
    ),
    rollback_webhook_secret: str = typer.Option(
        "",
        "--rollback-webhook-secret",
        help="Rollback webhook secret (falls back to FASTAGENT_ROLLBACK_WEBHOOK_SECRET).",
    ),
    rollback_timeout: float = typer.Option(15.0, "--rollback-timeout", help="Rollback webhook timeout in seconds."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional decision report output."),
) -> None:
    if target_phase <= 0:
        console.print("[red]Error:[/red] --target-phase must be > 0")
        raise typer.Exit(code=1)
    if rollback_timeout <= 0:
        console.print("[red]Error:[/red] --rollback-timeout must be > 0")
        raise typer.Exit(code=1)
    if min_phase_increment <= 0:
        console.print("[red]Error:[/red] --min-phase-increment must be > 0")
        raise typer.Exit(code=1)
    if max_phase_increment < min_phase_increment:
        console.print("[red]Error:[/red] --max-phase-increment must be >= --min-phase-increment")
        raise typer.Exit(code=1)
    if stability_window < 1:
        console.print("[red]Error:[/red] --stability-window must be >= 1")
        raise typer.Exit(code=1)
    if not (0 <= hold_risk_threshold <= 1):
        console.print("[red]Error:[/red] --hold-risk-threshold must be between 0 and 1")
        raise typer.Exit(code=1)

    try:
        plan = parse_phase_plan(phase_plan)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    try:
        state = load_rollout_state(state_file, plan=plan)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    canary_data = _load_optional_report(canary_report, "canary")
    shadow_data = _load_optional_report(shadow_report, "shadow")

    passed, reasons = evaluate_rollout_reports(canary_report=canary_data, shadow_report=shadow_data)
    risk_score = estimate_rollout_risk(canary_report=canary_data, shadow_report=shadow_data)
    decision = decide_rollout(
        state=state,
        passed=passed,
        reasons=reasons,
        target_phase=target_phase,
        adaptive=adaptive,
        risk_score=risk_score,
        min_phase_increment=min_phase_increment,
        max_phase_increment=max_phase_increment,
        stability_window=stability_window,
        hold_risk_threshold=hold_risk_threshold,
    )
    state = apply_rollout_decision(state, decision, deployment_id=deployment_id)
    save_rollout_state(state_file, state)

    webhook_result: dict = {"attempted": False}
    if decision.rollback_recommended and rollback_on_fail:
        resolved_url = rollback_webhook_url.strip() or os.getenv("FASTAGENT_ROLLBACK_WEBHOOK_URL", "").strip()
        resolved_secret = rollback_webhook_secret.strip() or os.getenv("FASTAGENT_ROLLBACK_WEBHOOK_SECRET", "").strip()
        if resolved_url and resolved_secret:
            payload = build_rollback_payload(
                deployment_id=deployment_id,
                reason="rollout_controller_failed",
                metadata={"reasons": decision.reasons, "phase": decision.current_phase},
                canary_report=canary_data or {},
            )
            webhook_result = {"attempted": True, "url": resolved_url}
            try:
                status_code, response_text = post_rollback_webhook(
                    url=resolved_url,
                    payload=payload,
                    secret=resolved_secret,
                    timeout=rollback_timeout,
                )
                webhook_result["status_code"] = status_code
                webhook_result["response"] = response_text
            except Exception as exc:
                webhook_result["error"] = str(exc)

    table = Table(title="FastAgent Rollout Controller")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("state_file", str(state_file))
    table.add_row("action", decision.action)
    table.add_row("adaptive", "yes" if decision.adaptive else "no")
    table.add_row("risk_score", str(decision.risk_score))
    table.add_row("phase_step", str(decision.phase_step))
    table.add_row("current_phase", str(decision.current_phase))
    table.add_row("next_phase", str(decision.next_phase))
    table.add_row("status", state.status)
    table.add_row("rollback_recommended", "yes" if decision.rollback_recommended else "no")
    table.add_row("reasons", " | ".join(decision.reasons) if decision.reasons else "none")
    console.print(table)

    report = {
        "decision": decision.to_dict(),
        "state": state.to_dict(),
        "webhook": webhook_result,
        "inputs": {
            "canary_report": str(canary_report) if canary_report is not None else "",
            "shadow_report": str(shadow_report) if shadow_report is not None else "",
            "phase_plan": plan,
            "target_phase": target_phase,
            "adaptive": adaptive,
            "risk_score": risk_score,
            "min_phase_increment": min_phase_increment,
            "max_phase_increment": max_phase_increment,
            "stability_window": stability_window,
            "hold_risk_threshold": hold_risk_threshold,
            "deployment_id": deployment_id,
        },
    }
    if output_json is not None:
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"[green]Rollout report written:[/green] {output_json}")

    if decision.rollback_recommended:
        raise typer.Exit(code=2)


def _load_optional_report(path: Path | None, label: str) -> dict | None:
    if path is None:
        return None
    if not path.exists():
        raise typer.BadParameter(f"{label} report not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid {label} report JSON: {exc}")
    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{label} report must be a JSON object")
    return payload
