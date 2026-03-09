from pathlib import Path
import subprocess
import sys

import typer
from rich.console import Console

console = Console()


def _has_docker_compose() -> bool:
    result = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def run_project(
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Generated project path."),
    host: str = typer.Option("127.0.0.1", "--host", help="Host for uvicorn."),
    port: int = typer.Option(8000, "--port", help="Port for uvicorn."),
    reload: bool = typer.Option(True, "--reload/--no-reload", help="Enable hot reload."),
    docker: bool = typer.Option(False, "--docker", help="Run using docker compose."),
    detach: bool = typer.Option(False, "--detach", help="Run docker compose in detached mode."),
) -> None:
    if detach and not docker:
        console.print("[red]Error:[/red] --detach can only be used with --docker.")
        raise typer.Exit(code=1)

    if docker:
        compose_file = project_path / "docker-compose.yml"
        if not compose_file.exists():
            console.print("[red]Error:[/red] docker-compose.yml not found in project path.")
            raise typer.Exit(code=1)

        if not _has_docker_compose():
            console.print("[red]Error:[/red] Docker Compose is not available. Install Docker Desktop or docker compose plugin.")
            raise typer.Exit(code=1)

        command = ["docker", "compose", "-f", str(compose_file), "up", "--build"]
        if detach:
            command.append("-d")

        console.print(f"[cyan]Running:[/cyan] {' '.join(command)}")
        result = subprocess.run(command, cwd=str(project_path))
        raise typer.Exit(code=result.returncode)

    if not (project_path / "app" / "main.py").exists():
        console.print("[red]Error:[/red] app/main.py not found in project path.")
        raise typer.Exit(code=1)

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")

    console.print(f"[cyan]Running:[/cyan] {' '.join(command)}")
    result = subprocess.run(command, cwd=str(project_path))
    raise typer.Exit(code=result.returncode)