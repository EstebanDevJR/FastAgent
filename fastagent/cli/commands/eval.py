import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from fastagent.evaluation.evaluator import score_predictions
from fastagent.evaluation.gate import evaluate_gate, load_eval_config, thresholds_from_config
from fastagent.evaluation.io import load_jsonl_records
from fastagent.evaluation.judge import JudgeResult, load_rubric, score_with_judge

console = Console()


def eval_project(
    dataset: Path = typer.Option(Path("eval_dataset.jsonl"), "--dataset", help="JSONL dataset with expected/predicted fields."),
    config: Path | None = typer.Option(None, "--config", help="Eval-as-code JSON config path."),
    gate: bool = typer.Option(False, "--gate", help="Apply thresholds gate (CI friendly)."),
    judge: bool = typer.Option(False, "--judge", help="Enable reproducible LLM-as-judge scoring."),
    judge_seed: int = typer.Option(42, "--judge-seed", help="Seed used for reproducible judge scoring."),
    judge_rubric: Path | None = typer.Option(None, "--judge-rubric", help="Optional JSON rubric path for judge mode."),
    output_json: Path | None = typer.Option(None, "--output-json", help="Optional JSON report output path."),
) -> None:
    config_data: dict | None = None
    if config is not None:
        try:
            config_data = load_eval_config(config)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)
        dataset_from_config = config_data.get("dataset")
        if isinstance(dataset_from_config, str) and dataset_from_config.strip():
            dataset = Path(dataset_from_config)

        judge_cfg = config_data.get("judge")
        if isinstance(judge_cfg, dict):
            if not judge:
                judge = bool(judge_cfg.get("enabled", False))
            if judge_seed == 42 and "seed" in judge_cfg:
                judge_seed = int(judge_cfg.get("seed", 42))
            if judge_rubric is None:
                rubric_path = judge_cfg.get("rubric_path")
                if isinstance(rubric_path, str) and rubric_path.strip():
                    judge_rubric = Path(rubric_path)

    try:
        records = load_jsonl_records(dataset)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        if "Dataset not found" in str(exc):
            console.print("Example: {\"expected\": \"answer\", \"predicted\": \"answer\"}")
        raise typer.Exit(code=1)

    if not records:
        console.print("[yellow]No evaluation records found in dataset.[/yellow]")
        raise typer.Exit(code=1)

    metrics = score_predictions(records)
    judge_result: JudgeResult | None = None
    if judge:
        rubric_inline = None
        if config_data and isinstance(config_data.get("judge"), dict):
            rubric_candidate = config_data["judge"].get("rubric")
            if isinstance(rubric_candidate, dict):
                rubric_inline = rubric_candidate
        try:
            if judge_rubric is not None:
                rubric = load_rubric(rubric_path=judge_rubric)
            else:
                rubric = load_rubric(rubric_inline=rubric_inline)
        except (FileNotFoundError, ValueError) as exc:
            console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)
        judge_result = score_with_judge(records, seed=judge_seed, rubric=rubric)

    table = Table(title="FastAgent Evaluation")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("accuracy", str(metrics.accuracy))
    table.add_row("reasoning quality", str(metrics.reasoning_quality))
    table.add_row("tool usage", str(metrics.tool_usage))
    table.add_row("hallucinations", str(metrics.hallucinations))
    table.add_row("cost", f"${metrics.cost}")
    console.print(table)

    if judge_result is not None:
        judge_table = Table(title="FastAgent Judge")
        judge_table.add_column("Metric", style="cyan")
        judge_table.add_column("Value", style="green")
        judge_table.add_row("seed", str(judge_result.seed))
        judge_table.add_row("overall_score", str(judge_result.overall_score))
        for name, value in judge_result.criteria_scores.items():
            judge_table.add_row(f"criterion:{name}", str(value))
        console.print(judge_table)

    report = {"dataset": str(dataset), "metrics": metrics.to_dict()}
    if judge_result is not None:
        report["judge"] = judge_result.to_dict()
    exit_code = 0

    if gate:
        thresholds = thresholds_from_config(config_data or {})
        gate_result = evaluate_gate(
            metrics,
            thresholds,
            judge_score=judge_result.overall_score if judge_result is not None else None,
        )

        gate_table = Table(title="FastAgent Eval Gate")
        gate_table.add_column("Result", style="cyan")
        gate_table.add_column("Details", style="green")
        gate_table.add_row("status", "PASS" if gate_result.passed else "FAIL")
        if gate_result.reasons:
            gate_table.add_row("reasons", " | ".join(gate_result.reasons))
        else:
            gate_table.add_row("reasons", "all thresholds satisfied")
        console.print(gate_table)

        report["gate"] = {
            "passed": gate_result.passed,
            "reasons": gate_result.reasons,
            "thresholds": thresholds.__dict__,
        }
        if not gate_result.passed:
            exit_code = 2

    if output_json is None and config_data:
        config_report = config_data.get("report_path")
        if isinstance(config_report, str) and config_report.strip():
            output_json = Path(config_report)

    if output_json is not None:
        output_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        console.print(f"[green]Eval report written:[/green] {output_json}")

    if exit_code != 0:
        raise typer.Exit(code=exit_code)
