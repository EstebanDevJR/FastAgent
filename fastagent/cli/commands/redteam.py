from pathlib import Path

import typer
from rich.console import Console

from fastagent.evaluation.redteam import generate_redteam_cases, write_redteam_jsonl

console = Console()


def generate_redteam(
    output: Path = typer.Option(Path("redteam_dataset.jsonl"), "--output", help="Output JSONL path."),
    count: int = typer.Option(50, "--count", help="Number of red-team cases."),
    domain: str = typer.Option("general assistants", "--domain", help="Target domain/context."),
    seed: int = typer.Option(42, "--seed", help="Random seed."),
) -> None:
    if count <= 0:
        console.print("[red]Error:[/red] --count must be > 0")
        raise typer.Exit(code=1)

    cases = generate_redteam_cases(domain=domain, count=count, seed=seed)
    write_redteam_jsonl(output, cases)
    console.print(f"[green]Red-team dataset written:[/green] {output} ({len(cases)} cases)")

