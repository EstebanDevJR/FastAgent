from pathlib import Path
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from fastagent.generators.project_generator import generate_project
from fastagent.prompts.questions import collect_project_config
from fastagent.utils.config import (
    ARCHITECT_OPENAI_MODE_OPTIONS,
    ARCHITECT_PROVIDER_OPTIONS,
    PROJECT_TYPE_OPTIONS,
    slugify_project_name,
)

console = Console()


def create_project(
    project_name: str = typer.Argument(..., help="Directory name for the new project."),
    project_type: str = typer.Option("chat", "--type", help="chat | rag | multi-agent | tool-agent | custom"),
    description: str = typer.Option("", "--description", help="Describe your agent idea."),
    architect_provider: str = typer.Option("local", "--architect-provider", help="local | openai | ollama"),
    architect_model: str = typer.Option("", "--architect-model", help="Model for architect provider."),
    architect_openai_mode: str = typer.Option("auto", "--architect-openai-mode", help="auto | responses | chat"),
    architect_timeout: int = typer.Option(20, "--architect-timeout", help="Timeout in seconds for architect provider calls."),
    architect_retries: int = typer.Option(2, "--architect-retries", help="Retries for architect provider calls."),
    architect_backoff: float = typer.Option(0.5, "--architect-backoff", help="Exponential backoff base in seconds."),
    architect_cache: bool = typer.Option(True, "--architect-cache/--no-architect-cache", help="Enable architect cache."),
    architect_cache_ttl: int = typer.Option(3600, "--architect-cache-ttl", help="Architect cache TTL in seconds."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip prompts and use defaults."),
    install: bool = typer.Option(False, "--install", help="Install generated project dependencies."),
    output_dir: Path = typer.Option(Path.cwd(), "--output-dir", help="Directory where the project will be created."),
) -> None:
    normalized_provider = architect_provider.strip().lower()
    if normalized_provider not in ARCHITECT_PROVIDER_OPTIONS:
        console.print(f"[red]Error:[/red] --architect-provider must be one of {', '.join(ARCHITECT_PROVIDER_OPTIONS)}")
        raise typer.Exit(code=1)

    normalized_type = project_type.strip().lower()
    if normalized_type not in PROJECT_TYPE_OPTIONS:
        console.print(f"[red]Error:[/red] --type must be one of {', '.join(PROJECT_TYPE_OPTIONS)}")
        raise typer.Exit(code=1)
    if architect_openai_mode.strip().lower() not in ARCHITECT_OPENAI_MODE_OPTIONS:
        console.print(
            f"[red]Error:[/red] --architect-openai-mode must be one of {', '.join(ARCHITECT_OPENAI_MODE_OPTIONS)}"
        )
        raise typer.Exit(code=1)

    if architect_timeout <= 0:
        console.print("[red]Error:[/red] --architect-timeout must be > 0")
        raise typer.Exit(code=1)
    if architect_retries < 0:
        console.print("[red]Error:[/red] --architect-retries must be >= 0")
        raise typer.Exit(code=1)
    if architect_backoff < 0:
        console.print("[red]Error:[/red] --architect-backoff must be >= 0")
        raise typer.Exit(code=1)
    if architect_cache_ttl < 0:
        console.print("[red]Error:[/red] --architect-cache-ttl must be >= 0")
        raise typer.Exit(code=1)

    slug = slugify_project_name(project_name)
    if not slug:
        console.print("[red]Error:[/red] project name must include at least one alphanumeric character")
        raise typer.Exit(code=1)

    config, recommendation = collect_project_config(
        project_name=project_name,
        assume_defaults=yes,
        project_type=normalized_type,
        description=description,
        architect_provider=normalized_provider,
        architect_model=architect_model or None,
        architect_timeout=architect_timeout,
        architect_retries=architect_retries,
        architect_backoff=architect_backoff,
        architect_openai_mode=architect_openai_mode.strip().lower(),
        architect_cache_enabled=architect_cache,
        architect_cache_ttl_seconds=architect_cache_ttl,
    )

    table = Table(title="Project Architect AI Recommendation")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Architect provider", recommendation.architect_provider)
    table.add_row("Architect model", recommendation.architect_model)
    if recommendation.architect_provider == "openai":
        table.add_row("OpenAI mode", architect_openai_mode.strip().lower())
    table.add_row("Agent type", recommendation.project_type)
    table.add_row("Vector DB", recommendation.vector_db)
    table.add_row("Tools", ", ".join(recommendation.tools) if recommendation.tools else "None")
    table.add_row("Memory", recommendation.memory_type)
    table.add_row("Evaluation", "enabled" if recommendation.evaluation_enabled else "disabled")
    table.add_row("Tracing", recommendation.tracing)
    table.add_row("Suggested models", ", ".join(recommendation.suggested_models))
    if recommendation.notes:
        table.add_row("Notes", " | ".join(recommendation.notes))
    console.print(table)

    target_dir = output_dir / config.project_slug
    if target_dir.exists() and any(target_dir.iterdir()):
        console.print(f"[red]Error:[/red] target directory '{target_dir}' is not empty.")
        raise typer.Exit(code=1)

    generate_project(config=config, target_dir=target_dir)
    console.print(f"[green]Project created:[/green] {target_dir}")

    if install:
        console.print("[cyan]Installing dependencies...[/cyan]")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print("[yellow]Dependency installation failed. Run manually:[/yellow]")
            console.print(result.stderr.strip())
        else:
            console.print("[green]Dependencies installed successfully.[/green]")

    console.print("\n[bold]Next steps[/bold]")
    console.print(f"cd {target_dir}")
    console.print("pip install -r requirements.txt")
    console.print("uvicorn app.main:app --reload")
