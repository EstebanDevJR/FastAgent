from pathlib import Path
import json

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.canary import CanaryThresholds, compare_canary_reports, load_report_json

console = Console()


def canary_check(
    baseline_report: Path = typer.Option(..., "--baseline-report", help="Baseline eval report JSON."),
    candidate_report: Path = typer.Option(..., "--candidate-report", help="Candidate eval report JSON."),
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
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional output report path."),
) -> None:
    try:
        baseline = load_report_json(baseline_report)
        candidate = load_report_json(candidate_report)
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
    result = compare_canary_reports(
        baseline=baseline,
        candidate=candidate,
        thresholds=thresholds,
        require_judge=require_judge,
    )

    table = Table(title="FastAgent Canary Check")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("status", "PASS" if result.passed else "FAIL")
    table.add_row("rollback_recommended", "yes" if result.rollback_recommended else "no")
    for key, value in result.deltas.items():
        table.add_row(key, str(value))
    if result.reasons:
        table.add_row("reasons", " | ".join(result.reasons))
    else:
        table.add_row("reasons", "within thresholds")
    console.print(table)

    if output_json is not None:
        payload = {
            "passed": result.passed,
            "rollback_recommended": result.rollback_recommended,
            "deltas": result.deltas,
            "reasons": result.reasons,
            "thresholds": thresholds.__dict__,
            "baseline_report": str(baseline_report),
            "candidate_report": str(candidate_report),
        }
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[green]Canary report written:[/green] {output_json}")

    if not result.passed:
        raise typer.Exit(code=2)
