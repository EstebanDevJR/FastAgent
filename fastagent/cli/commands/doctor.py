from dataclasses import dataclass
from pathlib import Path
import platform
import shutil
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from fastagent.utils.project import is_fastagent_project, plugin_manifest_path


console = Console()


@dataclass
class CheckResult:
    name: str
    status: str
    message: str


def _dependency_check(module_name: str) -> CheckResult:
    try:
        __import__(module_name)
        return CheckResult(module_name, "PASS", "installed")
    except Exception as exc:
        return CheckResult(module_name, "FAIL", f"missing ({exc})")


def _docker_check() -> CheckResult:
    if shutil.which("docker") is None:
        return CheckResult("docker", "WARN", "docker command not found")

    result = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if result.returncode != 0:
        return CheckResult("docker compose", "WARN", "docker compose plugin unavailable")
    return CheckResult("docker compose", "PASS", result.stdout.strip().splitlines()[0])


def run_doctor(
    project_path: Path = typer.Option(Path.cwd(), "--project-path", help="Project path to check."),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero on WARN or FAIL."),
) -> None:
    checks: list[CheckResult] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append(CheckResult("python", "PASS" if py_ok else "FAIL", platform.python_version()))

    for dep in ["typer", "rich", "questionary", "jinja2", "httpx"]:
        checks.append(_dependency_check(dep))

    checks.append(_docker_check())

    if is_fastagent_project(project_path):
        checks.append(CheckResult("project", "PASS", "FastAgent project detected"))
        env_exists = (project_path / ".env").exists()
        checks.append(CheckResult(".env", "PASS" if env_exists else "WARN", "present" if env_exists else "missing"))
        manifest_exists = plugin_manifest_path(project_path).exists()
        checks.append(
            CheckResult(
                "plugins manifest",
                "PASS" if manifest_exists else "WARN",
                "present" if manifest_exists else "missing",
            )
        )
    else:
        checks.append(CheckResult("project", "WARN", "not a FastAgent project at this path"))

    table = Table(title="FastAgent Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="green")

    for item in checks:
        color = "green" if item.status == "PASS" else ("yellow" if item.status == "WARN" else "red")
        table.add_row(item.name, f"[{color}]{item.status}[/{color}]", item.message)

    console.print(table)

    failed = [c for c in checks if c.status == "FAIL"]
    warned = [c for c in checks if c.status == "WARN"]

    if failed:
        raise typer.Exit(code=1)
    if strict and warned:
        raise typer.Exit(code=2)