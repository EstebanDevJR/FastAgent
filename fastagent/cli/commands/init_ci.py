from pathlib import Path
import json

import typer
from rich.console import Console
from rich.table import Table

from fastagent.utils.project import ensure_project

console = Console()


def _workflow_content(python_version: str) -> str:
    return f"""name: fastagent-eval-gate

on:
  push:
    branches: ["main", "master"]
  pull_request:
  workflow_dispatch:

jobs:
  eval-gate:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "{python_version}"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          pip install fastagent

      - name: Run FastAgent eval gate
        run: |
          fastagent eval --config fastagent.eval.json --gate --judge --judge-seed 42 --output-json eval_report.json

      - name: Canary quality check (if baseline exists)
        run: |
          if [ -f baseline_eval.json ] && [ -f eval_report.json ]; then
            fastagent canary-check --baseline-report baseline_eval.json --candidate-report eval_report.json --output-json canary_report.json
          else
            echo "baseline_eval.json not found, skipping canary-check"
          fi

      - name: Shadow traffic canary check (optional)
        if: env.FASTAGENT_BASELINE_URL != '' && env.FASTAGENT_CANDIDATE_URL != ''
        env:
          FASTAGENT_BASELINE_URL: ${{ secrets.FASTAGENT_BASELINE_URL }}
          FASTAGENT_CANDIDATE_URL: ${{ secrets.FASTAGENT_CANDIDATE_URL }}
        run: |
          fastagent canary-shadow \
            --baseline-url "$FASTAGENT_BASELINE_URL" \
            --candidate-url "$FASTAGENT_CANDIDATE_URL" \
            --sample-file examples/shadow_samples.sample.jsonl \
            --output-json shadow_report.json

      - name: Verify plugin audit log signatures
        run: |
          fastagent verify-audit --log-file logs/plugin_audit.jsonl --allow-missing

      - name: Trigger rollback webhook on failure
        if: failure() && env.FASTAGENT_ROLLBACK_WEBHOOK_URL != ''
        env:
          FASTAGENT_ROLLBACK_WEBHOOK_URL: ${{ secrets.FASTAGENT_ROLLBACK_WEBHOOK_URL }}
          FASTAGENT_ROLLBACK_WEBHOOK_SECRET: ${{ secrets.FASTAGENT_ROLLBACK_WEBHOOK_SECRET }}
        run: |
          fastagent rollback-webhook \
            --url "$FASTAGENT_ROLLBACK_WEBHOOK_URL" \
            --secret "$FASTAGENT_ROLLBACK_WEBHOOK_SECRET" \
            --deployment-id "${{ github.sha }}" \
            --reason "ci_quality_gate_failed" \
            --canary-report canary_report.json

      - name: Rollout controller decision (if canary/shadow reports exist)
        run: |
          if [ -f canary_report.json ]; then
            if [ -f shadow_report.json ]; then
              fastagent rollout-controller \
                --state-file rollout.state.json \
                --adaptive \
                --canary-report canary_report.json \
                --shadow-report shadow_report.json \
                --deployment-id "${{ github.sha }}" \
                --output-json rollout_decision.json
            else
              fastagent rollout-controller \
                --state-file rollout.state.json \
                --adaptive \
                --canary-report canary_report.json \
                --deployment-id "${{ github.sha }}" \
                --output-json rollout_decision.json
            fi
          else
            echo "No canary report found, skipping rollout-controller"
          fi

      - name: Apply rollout traffic weight (optional)
        if: env.FASTAGENT_ROLLOUT_PROVIDER != '' && env.FASTAGENT_ROLLOUT_RESOURCE != '' && env.FASTAGENT_APPLY_TRAFFIC == 'true'
        env:
          FASTAGENT_ROLLOUT_PROVIDER: ${{ secrets.FASTAGENT_ROLLOUT_PROVIDER }}
          FASTAGENT_ROLLOUT_RESOURCE: ${{ secrets.FASTAGENT_ROLLOUT_RESOURCE }}
          FASTAGENT_ROLLOUT_NAMESPACE: ${{ secrets.FASTAGENT_ROLLOUT_NAMESPACE }}
          FASTAGENT_ROLLOUT_BASELINE_BACKEND: ${{ secrets.FASTAGENT_ROLLOUT_BASELINE_BACKEND }}
          FASTAGENT_ROLLOUT_CANDIDATE_BACKEND: ${{ secrets.FASTAGENT_ROLLOUT_CANDIDATE_BACKEND }}
          FASTAGENT_APPLY_TRAFFIC: ${{ vars.FASTAGENT_APPLY_TRAFFIC }}
        run: |
          fastagent rollout-apply \
            --decision-report rollout_decision.json \
            --provider "$FASTAGENT_ROLLOUT_PROVIDER" \
            --resource "$FASTAGENT_ROLLOUT_RESOURCE" \
            --namespace "${{FASTAGENT_ROLLOUT_NAMESPACE:-default}}" \
            --baseline-backend "${{FASTAGENT_ROLLOUT_BASELINE_BACKEND:-baseline-svc}}" \
            --candidate-backend "${{FASTAGENT_ROLLOUT_CANDIDATE_BACKEND:-candidate-svc}}" \
            --execute \
            --output-json rollout_apply_report.json

      - name: Upload eval report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: fastagent-eval-report
          path: eval_report.json
          if-no-files-found: ignore

      - name: Upload plugin audit log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: fastagent-plugin-audit-log
          path: logs/plugin_audit.jsonl
          if-no-files-found: ignore

      - name: Upload canary report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: fastagent-canary-report
          path: canary_report.json
          if-no-files-found: ignore

      - name: Upload shadow report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: fastagent-shadow-report
          path: shadow_report.json
          if-no-files-found: ignore

      - name: Upload rollout decision
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: fastagent-rollout-decision
          path: rollout_decision.json
          if-no-files-found: ignore

      - name: Upload rollout apply report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: fastagent-rollout-apply
          path: rollout_apply_report.json
          if-no-files-found: ignore
"""


def _default_eval_config(dataset_path: str, report_path: str) -> dict:
    return {
        "dataset": dataset_path,
        "thresholds": {
            "accuracy_min": 0.8,
            "reasoning_quality_min": 0.8,
            "tool_usage_min": 0.0,
            "hallucinations_max": 0.3,
            "cost_max": 2.0,
        },
        "report_path": report_path,
    }


def _default_dataset_lines() -> list[str]:
    return [
        '{"expected":"hello","predicted":"hello there"}',
        '{"expected":"tool","predicted":"tool:search completed"}',
        '{"expected":"policy","predicted":"policy enabled and active"}',
    ]


def _default_shadow_lines() -> list[str]:
    return [
        '{"message":"Summarize key contract risks for this agreement."}',
        '{"message":"List top compliance issues in these terms."}',
        '{"message":"What are termination penalties in clause 7?"}',
    ]


def _write_if_needed(path: Path, content: str, overwrite: bool) -> tuple[bool, str]:
    if path.exists() and not overwrite:
        return False, "skipped (already exists)"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True, "written"


def init_ci(
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
    python_version: str = typer.Option("3.11", "--python-version", help="Python version for GitHub Actions."),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing files."),
    config_file: str = typer.Option("fastagent.eval.json", "--config-file", help="Eval config file path (relative to project root)."),
    dataset_file: str = typer.Option("examples/eval_dataset.sample.jsonl", "--dataset-file", help="Eval dataset JSONL path (relative to project root)."),
    shadow_dataset_file: str = typer.Option(
        "examples/shadow_samples.sample.jsonl",
        "--shadow-dataset-file",
        help="Shadow sample JSONL path (relative to project root).",
    ),
    report_file: str = typer.Option("eval_report.json", "--report-file", help="Eval report file path (relative to project root)."),
) -> None:
    try:
        ensure_project(project_path)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    workflow_path = project_path / ".github" / "workflows" / "fastagent-eval-gate.yml"
    config_path = project_path / config_file
    dataset_path = project_path / dataset_file
    shadow_dataset_path = project_path / shadow_dataset_file

    actions: list[tuple[str, str]] = []

    written, status = _write_if_needed(workflow_path, _workflow_content(python_version), overwrite)
    actions.append((str(workflow_path), status))

    config_content = json.dumps(_default_eval_config(dataset_file, report_file), indent=2) + "\n"
    written, status = _write_if_needed(config_path, config_content, overwrite)
    actions.append((str(config_path), status))

    dataset_content = "\n".join(_default_dataset_lines()) + "\n"
    written, status = _write_if_needed(dataset_path, dataset_content, overwrite)
    actions.append((str(dataset_path), status))

    shadow_content = "\n".join(_default_shadow_lines()) + "\n"
    written, status = _write_if_needed(shadow_dataset_path, shadow_content, overwrite)
    actions.append((str(shadow_dataset_path), status))

    table = Table(title="FastAgent CI Init")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")
    for item_path, item_status in actions:
        table.add_row(item_path, item_status)
    console.print(table)

    console.print("[green]CI files ready.[/green] Commit and push to activate GitHub Actions.")
