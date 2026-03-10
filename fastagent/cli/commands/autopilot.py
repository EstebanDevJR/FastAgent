from pathlib import Path
import json
import os

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.approval import (
    ensure_request_expiry,
    find_request,
    get_or_create_pending_request,
    is_request_expired,
    load_approval_state,
    mark_request_expired,
    record_request_escalation,
    save_approval_state,
    should_escalate_request,
)
from fastagent.deployment.autopilot_policy import (
    EnvironmentPolicy,
    PolicyEventDecision,
    decide_policy_event,
    load_environment_policy,
)
from fastagent.deployment.canary import CanaryThresholds, compare_canary_reports, load_report_json
from fastagent.deployment.rollout import (
    apply_rollout_decision,
    decide_rollout,
    estimate_rollout_risk,
    evaluate_rollout_reports,
    load_rollout_state,
    parse_phase_plan,
    save_rollout_state,
)
from fastagent.deployment.shadow import execute_shadow_live, load_shadow_messages, simulate_shadow, summarize_shadow
from fastagent.deployment.escalation import build_escalation_payload, detect_channel, post_escalation_notification
from fastagent.deployment.traffic import (
    TrafficApplyPlan,
    build_argo_command,
    build_gateway_patch,
    build_gateway_patch_command,
    execute_command,
    target_weight_from_report,
)
from fastagent.deployment.webhook import build_deployment_payload, post_signed_webhook, sign_payload

console = Console()

SHADOW_MODES = {"none", "simulate", "live"}
APPLY_PROVIDERS = {"none", "argo", "gateway"}
WEBHOOK_MODES = {"auto", "dry-run", "live"}
ESCALATION_MODES = {"auto", "dry-run", "live"}
ESCALATION_CHANNELS = {"auto", "slack", "teams", "generic"}


def autopilot(
    baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline eval report JSON."),
    candidate_report: Path = typer.Option(..., "--candidate-report", help="Candidate eval report JSON."),
    state_file: Path = typer.Option(Path("rollout.state.json"), "--state-file", help="Persistent rollout state file."),
    deployment_id: str = typer.Option("unknown", "--deployment-id", help="Deployment identifier."),
    phase_plan: str = typer.Option("5,25,50,100", "--phase-plan", help="Comma-separated phase percentages."),
    target_phase: int = typer.Option(100, "--target-phase", help="Target rollout phase percentage."),
    adaptive: bool = typer.Option(True, "--adaptive/--static", help="Enable adaptive phase jumps based on risk."),
    min_phase_increment: int = typer.Option(1, "--min-phase-increment", help="Minimum phase steps per advance."),
    max_phase_increment: int = typer.Option(2, "--max-phase-increment", help="Maximum phase steps per advance."),
    stability_window: int = typer.Option(2, "--stability-window", help="Successful windows needed before acceleration."),
    hold_risk_threshold: float = typer.Option(0.7, "--hold-risk-threshold", help="Risk threshold to hold rollout."),
    accuracy_drop_max: float = typer.Option(0.03, "--accuracy-drop-max", help="Max allowed accuracy drop."),
    reasoning_drop_max: float = typer.Option(0.05, "--reasoning-drop-max", help="Max allowed reasoning drop."),
    judge_drop_max: float = typer.Option(0.05, "--judge-drop-max", help="Max allowed judge score drop."),
    hallucinations_increase_max: float = typer.Option(
        0.05, "--hallucinations-increase-max", help="Max allowed hallucinations increase."
    ),
    cost_increase_ratio_max: float = typer.Option(
        0.25, "--cost-increase-ratio-max", help="Max allowed cost increase ratio."
    ),
    require_judge: bool = typer.Option(False, "--require-judge", help="Require judge score in reports."),
    shadow_mode: str = typer.Option("none", "--shadow-mode", help="none | simulate | live"),
    sample_file: Path | None = typer.Option(None, "--sample-file", help="JSONL prompts file for shadow mode."),
    simulate_count: int = typer.Option(25, "--simulate-count", help="Number of prompts when simulating without file."),
    simulate_degradation: float = typer.Option(0.15, "--simulate-degradation", help="Simulation degradation factor (0..1)."),
    seed: int = typer.Option(42, "--seed", help="Simulation seed."),
    baseline_url: str = typer.Option("", "--baseline-url", help="Baseline API base URL for live shadow mode."),
    candidate_url: str = typer.Option("", "--candidate-url", help="Candidate API base URL for live shadow mode."),
    endpoint: str = typer.Option("/chat", "--endpoint", help="Chat endpoint path for live shadow mode."),
    timeout: float = typer.Option(15.0, "--timeout", help="Request timeout for live mode."),
    max_disagreement_rate: float = typer.Option(0.25, "--max-disagreement-rate", help="Max allowed disagreement rate."),
    max_candidate_error_rate: float = typer.Option(0.1, "--max-candidate-error-rate", help="Max allowed candidate error rate."),
    max_latency_increase_ratio: float = typer.Option(
        0.3, "--max-latency-increase-ratio", help="Max allowed candidate latency increase ratio."
    ),
    apply_provider: str = typer.Option("none", "--apply-provider", help="none | argo | gateway"),
    apply_resource: str = typer.Option("", "--apply-resource", help="Rollout name (argo) or HTTPRoute name (gateway)."),
    namespace: str = typer.Option("default", "--namespace", help="Kubernetes namespace."),
    baseline_backend: str = typer.Option("baseline-svc", "--baseline-backend", help="Gateway baseline backend service name."),
    candidate_backend: str = typer.Option("candidate-svc", "--candidate-backend", help="Gateway candidate backend service name."),
    kubectl_bin: str = typer.Option("kubectl", "--kubectl-bin", help="kubectl binary path."),
    kube_context: str = typer.Option("", "--kube-context", help="Optional kube context."),
    apply_execute: bool = typer.Option(False, "--apply-execute", help="Actually apply traffic change (default dry-run)."),
    webhook: bool = typer.Option(False, "--webhook/--no-webhook", help="Emit signed deployment webhook."),
    webhook_url: str = typer.Option("", "--webhook-url", help="Webhook URL. Falls back to FASTAGENT_DEPLOY_WEBHOOK_URL."),
    webhook_secret: str = typer.Option(
        "",
        "--webhook-secret",
        help="Webhook secret. Falls back to FASTAGENT_DEPLOY_WEBHOOK_SECRET.",
    ),
    webhook_timeout: float = typer.Option(15.0, "--webhook-timeout", help="Webhook timeout in seconds."),
    webhook_environment: str = typer.Option("staging", "--webhook-environment", help="dev | staging | prod"),
    webhook_mode: str = typer.Option("auto", "--webhook-mode", help="auto | dry-run | live"),
    webhook_policy_file: Path | None = typer.Option(
        None,
        "--webhook-policy-file",
        help="Optional JSON file to override environment webhook policy.",
    ),
    approval_gate: bool = typer.Option(
        False,
        "--approval-gate/--no-approval-gate",
        help="Require manual approval when policy emits rollout_hold.",
    ),
    approval_state_file: Path = typer.Option(
        Path("rollout.approvals.json"),
        "--approval-state-file",
        help="Approval state store used by approval-list/approval-resolve.",
    ),
    approval_request_id: str = typer.Option(
        "",
        "--approval-request-id",
        help="Existing approval request ID to continue with an approved decision.",
    ),
    approval_ttl_minutes: int = typer.Option(
        60,
        "--approval-ttl-minutes",
        help="SLA window in minutes before approval request expires.",
    ),
    approval_escalation_url: str = typer.Option(
        "",
        "--approval-escalation-url",
        help="Escalation webhook URL (Slack/Teams/generic). Falls back to FASTAGENT_APPROVAL_ESCALATION_WEBHOOK_URL.",
    ),
    approval_escalation_secret: str = typer.Option(
        "",
        "--approval-escalation-secret",
        help="Optional escalation webhook signature secret (generic endpoints).",
    ),
    approval_escalation_mode: str = typer.Option(
        "auto",
        "--approval-escalation-mode",
        help="auto | dry-run | live",
    ),
    approval_escalation_channel: str = typer.Option(
        "auto",
        "--approval-escalation-channel",
        help="auto | slack | teams | generic",
    ),
    approval_escalation_timeout: float = typer.Option(
        15.0,
        "--approval-escalation-timeout",
        help="Escalation webhook timeout in seconds.",
    ),
    approval_escalation_cooldown_minutes: int = typer.Option(
        60,
        "--approval-escalation-cooldown-minutes",
        help="Min minutes between repeated escalation notifications for the same request.",
    ),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional output report path."),
) -> None:
    normalized_shadow_mode = shadow_mode.strip().lower()
    if normalized_shadow_mode not in SHADOW_MODES:
        console.print(f"[red]Error:[/red] --shadow-mode must be one of {', '.join(sorted(SHADOW_MODES))}")
        raise typer.Exit(code=1)

    normalized_apply_provider = apply_provider.strip().lower()
    if normalized_apply_provider not in APPLY_PROVIDERS:
        console.print(f"[red]Error:[/red] --apply-provider must be one of {', '.join(sorted(APPLY_PROVIDERS))}")
        raise typer.Exit(code=1)
    normalized_webhook_mode = webhook_mode.strip().lower()
    if normalized_webhook_mode not in WEBHOOK_MODES:
        console.print(f"[red]Error:[/red] --webhook-mode must be one of {', '.join(sorted(WEBHOOK_MODES))}")
        raise typer.Exit(code=1)
    normalized_escalation_mode = approval_escalation_mode.strip().lower()
    if normalized_escalation_mode not in ESCALATION_MODES:
        console.print(f"[red]Error:[/red] --approval-escalation-mode must be one of {', '.join(sorted(ESCALATION_MODES))}")
        raise typer.Exit(code=1)
    normalized_escalation_channel = approval_escalation_channel.strip().lower()
    if normalized_escalation_channel not in ESCALATION_CHANNELS:
        console.print(
            f"[red]Error:[/red] --approval-escalation-channel must be one of {', '.join(sorted(ESCALATION_CHANNELS))}"
        )
        raise typer.Exit(code=1)

    if target_phase <= 0:
        console.print("[red]Error:[/red] --target-phase must be > 0")
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
    if simulate_count <= 0:
        console.print("[red]Error:[/red] --simulate-count must be > 0")
        raise typer.Exit(code=1)
    if timeout <= 0:
        console.print("[red]Error:[/red] --timeout must be > 0")
        raise typer.Exit(code=1)
    if webhook_timeout <= 0:
        console.print("[red]Error:[/red] --webhook-timeout must be > 0")
        raise typer.Exit(code=1)
    if approval_ttl_minutes <= 0:
        console.print("[red]Error:[/red] --approval-ttl-minutes must be > 0")
        raise typer.Exit(code=1)
    if approval_escalation_timeout <= 0:
        console.print("[red]Error:[/red] --approval-escalation-timeout must be > 0")
        raise typer.Exit(code=1)
    if approval_escalation_cooldown_minutes <= 0:
        console.print("[red]Error:[/red] --approval-escalation-cooldown-minutes must be > 0")
        raise typer.Exit(code=1)

    try:
        baseline = load_report_json(baseline_report)
        candidate = load_report_json(candidate_report)
        plan = parse_phase_plan(phase_plan)
        state = load_rollout_state(state_file, plan=plan)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    thresholds = CanaryThresholds(
        accuracy_drop_max=accuracy_drop_max,
        reasoning_drop_max=reasoning_drop_max,
        judge_drop_max=judge_drop_max,
        hallucinations_increase_max=hallucinations_increase_max,
        cost_increase_ratio_max=cost_increase_ratio_max,
    )
    canary_result = compare_canary_reports(
        baseline=baseline,
        candidate=candidate,
        thresholds=thresholds,
        require_judge=require_judge,
    )
    canary_payload = {
        "passed": canary_result.passed,
        "rollback_recommended": canary_result.rollback_recommended,
        "deltas": canary_result.deltas,
        "reasons": canary_result.reasons,
        "thresholds": thresholds.__dict__,
        "baseline_report": str(baseline_report),
        "candidate_report": str(candidate_report),
    }

    shadow_payload: dict | None = None
    if normalized_shadow_mode != "none":
        messages = _resolve_shadow_messages(
            mode=normalized_shadow_mode,
            sample_file=sample_file,
            simulate_count=simulate_count,
        )
        if normalized_shadow_mode == "simulate":
            results = simulate_shadow(messages=messages, degradation=simulate_degradation, seed=seed)
        else:
            if not baseline_url.strip() or not candidate_url.strip():
                console.print("[red]Error:[/red] --baseline-url and --candidate-url are required for --shadow-mode live")
                raise typer.Exit(code=1)
            try:
                results = execute_shadow_live(
                    baseline_url=baseline_url.strip(),
                    candidate_url=candidate_url.strip(),
                    endpoint=endpoint,
                    messages=messages,
                    timeout=timeout,
                )
            except (RuntimeError, ValueError) as exc:
                console.print(f"[red]Error:[/red] {exc}")
                raise typer.Exit(code=1)
        shadow_summary = summarize_shadow(
            results=results,
            max_disagreement_rate=max_disagreement_rate,
            max_candidate_error_rate=max_candidate_error_rate,
            max_latency_increase_ratio=max_latency_increase_ratio,
        )
        shadow_payload = {
            "mode": normalized_shadow_mode,
            "summary": shadow_summary.to_dict(),
            "thresholds": {
                "max_disagreement_rate": max_disagreement_rate,
                "max_candidate_error_rate": max_candidate_error_rate,
                "max_latency_increase_ratio": max_latency_increase_ratio,
            },
        }

    passed, reasons = evaluate_rollout_reports(canary_report=canary_payload, shadow_report=shadow_payload)
    risk_score = estimate_rollout_risk(canary_report=canary_payload, shadow_report=shadow_payload)
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

    apply_report = _build_apply_report(
        provider=normalized_apply_provider,
        resource=apply_resource,
        namespace=namespace,
        baseline_backend=baseline_backend,
        candidate_backend=candidate_backend,
        kubectl_bin=kubectl_bin,
        kube_context=kube_context,
        execute=False,
        decision=decision.to_dict(),
        state=state.to_dict(),
    )
    policy_decision: PolicyEventDecision | None = None
    policy = None
    approval_report = _default_approval_report(enabled=approval_gate)
    if webhook or approval_gate:
        try:
            policy = load_environment_policy(webhook_environment, policy_file=webhook_policy_file)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)
        policy_decision = decide_policy_event(policy, decision=decision.to_dict(), apply_report=apply_report)

    if approval_gate:
        if policy is None or policy_decision is None:
            console.print("[red]Error:[/red] internal policy state is not initialized")
            raise typer.Exit(code=1)
        try:
            approval_report, policy_decision = _process_approval_gate(
                state_file=approval_state_file,
                request_id=approval_request_id,
                deployment_id=deployment_id,
                policy_environment=policy.environment,
                policy_decision=policy_decision,
                decision=decision.to_dict(),
                apply_report=apply_report,
                canary_payload=canary_payload,
                shadow_payload=shadow_payload,
                ttl_minutes=approval_ttl_minutes,
            )
        except (ValueError, typer.BadParameter) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)
        approval_report["escalation"] = _build_approval_escalation_report(enabled=False)
        try:
            approval_report["escalation"] = _process_approval_escalation(
                approval_report=approval_report,
                state_file=approval_state_file,
                deployment_id=deployment_id,
                policy_environment=policy.environment,
                escalation_url=approval_escalation_url,
                escalation_secret=approval_escalation_secret,
                escalation_mode=normalized_escalation_mode,
                escalation_channel=normalized_escalation_channel,
                escalation_timeout=approval_escalation_timeout,
                escalation_cooldown_minutes=approval_escalation_cooldown_minutes,
            )
        except (ValueError, typer.BadParameter) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)

    if apply_execute and apply_report.get("enabled") and (policy_decision is None or policy_decision.event == "promotion_requested"):
        apply_report = _execute_apply_plan(apply_report)

    try:
        if webhook:
            if policy is None or policy_decision is None:
                raise typer.BadParameter("webhook policy is not initialized")
            webhook_report = _build_webhook_report(
                enabled=True,
                webhook_url=webhook_url,
                webhook_secret=webhook_secret,
                webhook_mode=normalized_webhook_mode,
                webhook_timeout=webhook_timeout,
                deployment_id=deployment_id,
                decision=decision.to_dict(),
                state=state.to_dict(),
                apply_report=apply_report,
                canary_payload=canary_payload,
                shadow_payload=shadow_payload,
                policy=policy,
                policy_decision=policy_decision,
            )
        else:
            webhook_report = _default_webhook_report(enabled=False)
    except (FileNotFoundError, ValueError, typer.BadParameter) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    table = Table(title="FastAgent Autopilot")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("canary", "PASS" if canary_result.passed else "FAIL")
    table.add_row("shadow_mode", normalized_shadow_mode)
    table.add_row("shadow", "PASS" if _shadow_passed(shadow_payload) else ("SKIPPED" if shadow_payload is None else "FAIL"))
    table.add_row("rollout_action", decision.action)
    table.add_row("phase", f"{decision.current_phase} -> {decision.next_phase}")
    table.add_row("risk_score", str(decision.risk_score))
    table.add_row("traffic_apply", "enabled" if apply_report["enabled"] else "disabled")
    if apply_report["enabled"]:
        table.add_row("apply_mode", "execute" if apply_report.get("executed", False) else "dry-run")
        table.add_row("target_weight", str(apply_report["plan"]["target_weight"]))
    table.add_row("approval_gate", "enabled" if approval_report.get("enabled", False) else "disabled")
    if approval_report.get("enabled", False):
        table.add_row("approval_status", str(approval_report.get("status", "n/a")))
        table.add_row("approval_request_id", str(approval_report.get("request_id", "")))
        table.add_row("approval_expires_at", str(approval_report.get("expires_at", "")))
        escalation = approval_report.get("escalation", {})
        if isinstance(escalation, dict):
            table.add_row("approval_escalation", str(escalation.get("status", "disabled")))
    table.add_row("webhook", "enabled" if webhook_report["enabled"] else "disabled")
    if webhook_report["enabled"]:
        table.add_row("webhook_event", webhook_report.get("event", "n/a"))
        table.add_row("webhook_mode", "dry-run" if webhook_report.get("dry_run", False) else "live")
        table.add_row("webhook_sent", "yes" if webhook_report.get("sent", False) else "no")
    console.print(table)

    report = {
        "canary": canary_payload,
        "shadow": shadow_payload,
        "decision": decision.to_dict(),
        "state": state.to_dict(),
        "apply": apply_report,
        "approval": approval_report,
        "webhook": webhook_report,
        "inputs": {
            "state_file": str(state_file),
            "deployment_id": deployment_id,
            "phase_plan": plan,
            "target_phase": target_phase,
            "adaptive": adaptive,
            "shadow_mode": normalized_shadow_mode,
            "apply_provider": normalized_apply_provider,
            "webhook": webhook,
            "webhook_environment": webhook_environment,
            "webhook_mode": normalized_webhook_mode,
            "approval_gate": approval_gate,
            "approval_state_file": str(approval_state_file),
            "approval_request_id": approval_request_id,
            "approval_ttl_minutes": approval_ttl_minutes,
            "approval_escalation_mode": normalized_escalation_mode,
            "approval_escalation_channel": normalized_escalation_channel,
            "approval_escalation_url": bool(approval_escalation_url.strip()),
            "approval_escalation_cooldown_minutes": approval_escalation_cooldown_minutes,
        },
    }
    if output_json is not None:
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"[green]Autopilot report written:[/green] {output_json}")

    apply_status = int(apply_report.get("status_code", 0))
    if approval_report.get("enabled") and approval_report.get("status") == "pending":
        raise typer.Exit(code=5)
    if approval_report.get("enabled") and approval_report.get("status") == "expired":
        raise typer.Exit(code=7)
    if approval_report.get("enabled") and approval_report.get("status") == "rejected":
        raise typer.Exit(code=6)
    if apply_report.get("enabled") and apply_report.get("executed") and apply_status != 0:
        raise typer.Exit(code=3)
    webhook_status = int(webhook_report.get("status_code", 0))
    if webhook_report.get("enabled") and webhook_report.get("sent") and webhook_status >= 400:
        raise typer.Exit(code=4)
    if decision.rollback_recommended:
        raise typer.Exit(code=2)


def _resolve_shadow_messages(mode: str, sample_file: Path | None, simulate_count: int) -> list[str]:
    messages: list[str] = []
    if sample_file is not None:
        try:
            messages = load_shadow_messages(sample_file)
        except (FileNotFoundError, ValueError) as exc:
            raise typer.BadParameter(str(exc))
    if messages:
        return messages
    if mode in {"simulate", "live"}:
        return [f"autopilot_sample_{idx}" for idx in range(1, simulate_count + 1)]
    return []


def _shadow_passed(shadow_payload: dict | None) -> bool:
    if shadow_payload is None:
        return True
    summary = shadow_payload.get("summary")
    if not isinstance(summary, dict):
        return False
    return bool(summary.get("passed", False))


def _default_approval_report(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "required": False,
        "status": "disabled" if not enabled else "not_required",
        "request_id": "",
        "reason": "",
        "expired": False,
        "expires_at": "",
        "ttl_minutes": 0,
        "request": {},
        "escalation": _build_approval_escalation_report(enabled=False),
    }


def _default_webhook_report(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "sent": False,
        "status_code": 0,
        "response": "",
        "event": "",
        "reason": "",
        "dry_run": False,
        "should_send": False,
        "error": "",
        "signature": "",
        "policy": {},
        "payload": {},
    }


def _build_approval_escalation_report(enabled: bool) -> dict:
    return {
        "enabled": enabled,
        "status": "disabled" if not enabled else "skipped",
        "attempted": False,
        "sent": False,
        "dry_run": False,
        "channel": "",
        "url": "",
        "status_code": 0,
        "response": "",
        "error": "",
        "reason": "",
        "payload": {},
    }


def _process_approval_escalation(
    approval_report: dict,
    state_file: Path,
    deployment_id: str,
    policy_environment: str,
    escalation_url: str,
    escalation_secret: str,
    escalation_mode: str,
    escalation_channel: str,
    escalation_timeout: float,
    escalation_cooldown_minutes: int,
) -> dict:
    report = _build_approval_escalation_report(enabled=True)
    status = str(approval_report.get("status", "")).strip()
    report["reason"] = "approval_not_pending"
    if status not in {"pending", "expired"}:
        return report
    if not bool(approval_report.get("expired", False)) and status != "expired":
        report["status"] = "skipped"
        report["reason"] = "approval_not_expired"
        return report

    resolved_url = escalation_url.strip() or os.getenv("FASTAGENT_APPROVAL_ESCALATION_WEBHOOK_URL", "").strip()
    if not resolved_url:
        report["status"] = "skipped"
        report["reason"] = "missing_escalation_url"
        return report
    resolved_secret = escalation_secret.strip() or os.getenv("FASTAGENT_APPROVAL_ESCALATION_WEBHOOK_SECRET", "").strip()
    channel = detect_channel(resolved_url, channel=escalation_channel)

    state = load_approval_state(state_file)
    request_id = str(approval_report.get("request_id", "")).strip()
    request = find_request(state, request_id)
    if request is None:
        raise typer.BadParameter(f"approval request not found for escalation: {request_id}")
    if not should_escalate_request(request, cooldown_minutes=escalation_cooldown_minutes):
        report["status"] = "skipped"
        report["reason"] = "cooldown_active"
        report["channel"] = channel
        report["url"] = resolved_url
        return report

    dry_run = escalation_mode == "dry-run" or (escalation_mode == "auto" and policy_environment == "dev")
    payload = build_escalation_payload(
        channel=channel,
        deployment_id=deployment_id,
        environment=policy_environment,
        request=request,
        state_file=str(state_file),
    )

    status_code = 0
    response_text = ""
    error = ""
    attempted = True
    sent = False
    if dry_run:
        status = "dry_run"
    else:
        status = "sent"
        sent = True
        try:
            status_code, response_text = post_escalation_notification(
                url=resolved_url,
                payload=payload,
                timeout=escalation_timeout,
                secret=resolved_secret,
            )
        except Exception as exc:
            status_code, response_text = 599, ""
            error = str(exc)
        if status_code >= 400:
            status = "failed"

    record_request_escalation(
        request=request,
        channel=channel,
        url=resolved_url,
        dry_run=dry_run,
        attempted=attempted,
        sent=sent,
        status_code=int(status_code),
        error=error,
        response=response_text,
    )
    save_approval_state(state_file, state)
    approval_report["request"] = request

    report.update(
        {
            "status": status,
            "attempted": attempted,
            "sent": sent,
            "dry_run": dry_run,
            "channel": channel,
            "url": resolved_url,
            "status_code": int(status_code),
            "response": response_text,
            "error": error,
            "reason": "approval_expired_escalation",
            "payload": payload,
        }
    )
    return report


def _process_approval_gate(
    state_file: Path,
    request_id: str,
    deployment_id: str,
    policy_environment: str,
    policy_decision: PolicyEventDecision,
    decision: dict,
    apply_report: dict,
    canary_payload: dict,
    shadow_payload: dict | None,
    ttl_minutes: int,
) -> tuple[dict, PolicyEventDecision]:
    base = _default_approval_report(enabled=True)
    if policy_decision.event != "rollout_hold":
        base["status"] = "not_required"
        base["reason"] = "policy_not_hold"
        return base, policy_decision

    state = load_approval_state(state_file)
    req: dict | None = None

    if request_id.strip():
        req = find_request(state, request_id)
        if req is None:
            raise typer.BadParameter(f"approval request not found: {request_id}")
    else:
        req = get_or_create_pending_request(
            state=state,
            deployment_id=deployment_id,
            environment=policy_environment,
            reason=policy_decision.reason,
            decision=decision,
            apply_report=apply_report,
            canary_payload=canary_payload,
            shadow_payload=shadow_payload,
            ttl_minutes=ttl_minutes,
        )

    ensure_request_expiry(req, ttl_minutes=ttl_minutes)
    expired = is_request_expired(req)
    if expired:
        mark_request_expired(req, notes="approval_sla_expired")

    save_approval_state(state_file, state)
    status = str(req.get("status", "pending")).strip() or "pending"
    report = {
        "enabled": True,
        "required": True,
        "status": status,
        "request_id": str(req.get("id", "")),
        "reason": policy_decision.reason,
        "expired": status == "expired" or expired,
        "expires_at": str(req.get("expires_at", "")),
        "ttl_minutes": int(req.get("ttl_minutes", ttl_minutes)),
        "request": req,
        "state_file": str(state_file),
    }

    if status == "approved":
        override = PolicyEventDecision(
            event="promotion_requested",
            reason="manual_approval_override",
            should_send=True,
        )
        report["required"] = False
        report["reason"] = "manual_approval_override"
        return report, override
    if status == "rejected":
        report["required"] = False
        report["reason"] = "manual_approval_rejected"
        return report, policy_decision
    if status == "expired":
        report["required"] = False
        report["reason"] = "manual_approval_expired"
        return report, policy_decision
    return report, policy_decision


def _build_apply_report(
    provider: str,
    resource: str,
    namespace: str,
    baseline_backend: str,
    candidate_backend: str,
    kubectl_bin: str,
    kube_context: str,
    execute: bool,
    decision: dict,
    state: dict,
) -> dict:
    if provider == "none":
        return {"enabled": False, "executed": False, "status_code": 0, "stdout": "", "stderr": "", "plan": None}
    if not resource.strip():
        raise typer.BadParameter("--apply-resource is required when --apply-provider is not none")

    action, current_phase, target_weight = target_weight_from_report({"decision": decision, "state": state})
    plan = TrafficApplyPlan(
        action=action,
        current_phase=current_phase,
        target_weight=target_weight,
        provider=provider,
        resource=resource.strip(),
        namespace=namespace.strip() or "default",
    )

    if provider == "argo":
        plan.command = build_argo_command(
            rollout_name=plan.resource,
            weight=plan.target_weight,
            namespace=plan.namespace,
            kubectl_bin=kubectl_bin,
            kube_context=kube_context,
        )
    else:
        plan.patch = build_gateway_patch(
            baseline_backend=baseline_backend.strip(),
            candidate_backend=candidate_backend.strip(),
            candidate_weight=plan.target_weight,
        )
        plan.command = build_gateway_patch_command(
            route_name=plan.resource,
            namespace=plan.namespace,
            patch=plan.patch,
            kubectl_bin=kubectl_bin,
            kube_context=kube_context,
        )

    status_code = 0
    stdout = ""
    stderr = ""
    if execute:
        status_code, stdout, stderr = execute_command(plan.command or [])

    return {
        "enabled": True,
        "executed": execute,
        "status_code": status_code,
        "stdout": stdout,
        "stderr": stderr,
        "plan": plan.to_dict(),
    }


def _execute_apply_plan(apply_report: dict) -> dict:
    command = apply_report.get("plan", {}).get("command", [])
    if not isinstance(command, list) or not command:
        apply_report["executed"] = True
        apply_report["status_code"] = 1
        apply_report["stderr"] = "missing apply command"
        return apply_report
    status_code, stdout, stderr = execute_command(command)
    apply_report["executed"] = True
    apply_report["status_code"] = int(status_code)
    apply_report["stdout"] = stdout
    apply_report["stderr"] = stderr
    return apply_report


def _build_webhook_report(
    enabled: bool,
    webhook_url: str,
    webhook_secret: str,
    webhook_mode: str,
    webhook_timeout: float,
    deployment_id: str,
    decision: dict,
    state: dict,
    apply_report: dict,
    canary_payload: dict,
    shadow_payload: dict | None,
    policy: EnvironmentPolicy,
    policy_decision: PolicyEventDecision,
) -> dict:
    base_report = {
        "enabled": enabled,
        "sent": False,
        "status_code": 0,
        "response": "",
        "event": "",
        "reason": "",
        "dry_run": False,
        "signature": "",
        "policy": {},
        "payload": {},
    }
    if not enabled:
        return base_report

    resolved_url = webhook_url.strip() or os.getenv("FASTAGENT_DEPLOY_WEBHOOK_URL", "").strip()
    if not resolved_url:
        resolved_url = os.getenv("FASTAGENT_ROLLBACK_WEBHOOK_URL", "").strip()
    resolved_secret = webhook_secret.strip() or os.getenv("FASTAGENT_DEPLOY_WEBHOOK_SECRET", "").strip()
    if not resolved_secret:
        resolved_secret = os.getenv("FASTAGENT_ROLLBACK_WEBHOOK_SECRET", "").strip()
    if not resolved_url:
        raise typer.BadParameter("webhook URL is required (option or FASTAGENT_DEPLOY_WEBHOOK_URL)")
    if not resolved_secret:
        raise typer.BadParameter("webhook secret is required (option or FASTAGENT_DEPLOY_WEBHOOK_SECRET)")
    dry_run = webhook_mode == "dry-run" or (webhook_mode == "auto" and policy.webhook_dry_run_default)

    payload = build_deployment_payload(
        event=policy_decision.event,
        deployment_id=deployment_id,
        reason=policy_decision.reason,
        environment=policy.environment,
        metadata={
            "policy_environment": policy.environment,
            "policy_promote_max_risk": policy.promote_max_risk,
            "policy_require_apply_success_for_promote": policy.require_apply_success_for_promote,
            "policy_send_events": sorted(policy.send_events),
        },
        canary_report=canary_payload,
        shadow_report=shadow_payload or {},
        rollout_decision=decision,
        rollout_state=state,
    )
    signature = sign_payload(payload, secret=resolved_secret)

    report = {
        "enabled": True,
        "url": resolved_url,
        "sent": False,
        "status_code": 0,
        "response": "",
        "error": "",
        "event": policy_decision.event,
        "reason": policy_decision.reason,
        "dry_run": dry_run,
        "should_send": policy_decision.should_send,
        "signature": signature,
        "policy": {
            "environment": policy.environment,
            "promote_max_risk": policy.promote_max_risk,
            "require_apply_success_for_promote": policy.require_apply_success_for_promote,
            "send_events": sorted(policy.send_events),
            "webhook_dry_run_default": policy.webhook_dry_run_default,
        },
        "payload": payload,
    }

    if not policy_decision.should_send:
        return report
    if dry_run:
        return report

    try:
        status_code, response_text = post_signed_webhook(
            url=resolved_url,
            payload=payload,
            secret=resolved_secret,
            timeout=webhook_timeout,
            event_header=policy_decision.event,
        )
    except Exception as exc:
        status_code, response_text = 599, ""
        report["error"] = str(exc)
    report["sent"] = True
    report["status_code"] = status_code
    report["response"] = response_text
    return report
