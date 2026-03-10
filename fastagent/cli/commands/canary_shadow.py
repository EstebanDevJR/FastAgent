from pathlib import Path
import json

import typer
from rich.console import Console
from rich.table import Table

from fastagent.deployment.shadow import (
    execute_shadow_live,
    load_shadow_messages,
    simulate_shadow,
    summarize_shadow,
)

console = Console()


def canary_shadow(
    baseline_url: str = typer.Option("", "--baseline-url", help="Baseline API base URL."),
    candidate_url: str = typer.Option("", "--candidate-url", help="Candidate API base URL."),
    endpoint: str = typer.Option("/chat", "--endpoint", help="Chat endpoint path."),
    sample_file: Path | None = typer.Option(None, "--sample-file", help="JSONL prompts file."),
    simulate: bool = typer.Option(False, "--simulate", help="Run deterministic simulation mode (no network)."),
    simulate_count: int = typer.Option(25, "--simulate-count", help="Number of prompts when simulating without file."),
    simulate_degradation: float = typer.Option(
        0.15, "--simulate-degradation", help="Simulation degradation factor (0..1)."
    ),
    seed: int = typer.Option(42, "--seed", help="Simulation seed."),
    timeout: float = typer.Option(15.0, "--timeout", help="Request timeout for live mode."),
    max_disagreement_rate: float = typer.Option(0.25, "--max-disagreement-rate", help="Max allowed disagreement rate."),
    max_candidate_error_rate: float = typer.Option(
        0.1, "--max-candidate-error-rate", help="Max allowed candidate error rate."
    ),
    max_latency_increase_ratio: float = typer.Option(
        0.3, "--max-latency-increase-ratio", help="Max allowed candidate latency increase ratio."
    ),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional output report path."),
) -> None:
    if simulate_count <= 0:
        console.print("[red]Error:[/red] --simulate-count must be > 0")
        raise typer.Exit(code=1)
    if timeout <= 0:
        console.print("[red]Error:[/red] --timeout must be > 0")
        raise typer.Exit(code=1)

    messages: list[str]
    if sample_file is not None:
        try:
            messages = load_shadow_messages(sample_file)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)
    else:
        messages = []

    if not messages and simulate:
        messages = [f"shadow_sample_{idx}" for idx in range(1, simulate_count + 1)]
    if not messages:
        console.print("[red]Error:[/red] provide --sample-file or use --simulate")
        raise typer.Exit(code=1)

    if simulate:
        results = simulate_shadow(messages=messages, degradation=simulate_degradation, seed=seed)
    else:
        if not baseline_url.strip() or not candidate_url.strip():
            console.print("[red]Error:[/red] --baseline-url and --candidate-url are required in live mode.")
            raise typer.Exit(code=1)
        try:
            results = execute_shadow_live(
                baseline_url=baseline_url,
                candidate_url=candidate_url,
                endpoint=endpoint,
                messages=messages,
                timeout=timeout,
            )
        except (RuntimeError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)

    summary = summarize_shadow(
        results=results,
        max_disagreement_rate=max_disagreement_rate,
        max_candidate_error_rate=max_candidate_error_rate,
        max_latency_increase_ratio=max_latency_increase_ratio,
    )

    table = Table(title="FastAgent Canary Shadow")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("mode", "simulate" if simulate else "live")
    table.add_row("samples", str(summary.total))
    table.add_row("status", "PASS" if summary.passed else "FAIL")
    table.add_row("candidate_error_rate", str(summary.candidate_error_rate))
    table.add_row("disagreement_rate", str(summary.disagreement_rate))
    table.add_row("baseline_p95_ms", str(summary.baseline_p95_ms))
    table.add_row("candidate_p95_ms", str(summary.candidate_p95_ms))
    table.add_row("latency_increase_ratio", str(summary.latency_increase_ratio))
    table.add_row("reasons", " | ".join(summary.reasons) if summary.reasons else "within thresholds")
    console.print(table)

    if output_json is not None:
        payload = {
            "mode": "simulate" if simulate else "live",
            "baseline_url": baseline_url,
            "candidate_url": candidate_url,
            "endpoint": endpoint,
            "summary": summary.to_dict(),
            "thresholds": {
                "max_disagreement_rate": max_disagreement_rate,
                "max_candidate_error_rate": max_candidate_error_rate,
                "max_latency_increase_ratio": max_latency_increase_ratio,
            },
        }
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[green]Shadow report written:[/green] {output_json}")

    if not summary.passed:
        raise typer.Exit(code=2)
