from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys


@dataclass
class ReleaseCheck:
    name: str
    passed: bool
    severity: str
    details: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "details": self.details,
        }


def run_release_checks(project_path: Path, run_tests: bool = False) -> list[ReleaseCheck]:
    checks: list[ReleaseCheck] = []
    checks.extend(_check_required_files(project_path))
    checks.extend(_check_version_consistency(project_path))
    checks.extend(_check_pyproject_scripts(project_path))
    checks.extend(_check_tests_presence(project_path))
    checks.extend(_check_docs_presence(project_path))
    if run_tests:
        checks.append(_run_pytest(project_path))
    return checks


def _check_required_files(project_path: Path) -> list[ReleaseCheck]:
    required = [
        "README.md",
        "LICENSE",
        "pyproject.toml",
        "docs/quickstart.md",
        "docs/architecture.md",
        "fastagent/cli/main.py",
    ]
    checks: list[ReleaseCheck] = []
    for rel in required:
        path = project_path / rel
        checks.append(
            ReleaseCheck(
                name=f"file:{rel}",
                passed=path.exists(),
                severity="error",
                details="found" if path.exists() else "missing",
            )
        )
    return checks


def _check_version_consistency(project_path: Path) -> list[ReleaseCheck]:
    pyproject_path = project_path / "pyproject.toml"
    init_path = project_path / "fastagent" / "__init__.py"
    if not pyproject_path.exists() or not init_path.exists():
        return [
            ReleaseCheck(
                name="version-consistency",
                passed=False,
                severity="error",
                details="missing pyproject.toml or fastagent/__init__.py",
            )
        ]

    py_version = _extract_pyproject_version(pyproject_path.read_text(encoding="utf-8"))
    init_version = _extract_init_version(init_path.read_text(encoding="utf-8"))
    if not py_version or not init_version:
        return [
            ReleaseCheck(
                name="version-consistency",
                passed=False,
                severity="error",
                details="could not parse versions",
            )
        ]
    return [
        ReleaseCheck(
            name="version-consistency",
            passed=py_version == init_version,
            severity="error",
            details=f"pyproject={py_version}, package={init_version}",
        )
    ]


def _check_pyproject_scripts(project_path: Path) -> list[ReleaseCheck]:
    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.exists():
        return [ReleaseCheck(name="pyproject-scripts", passed=False, severity="error", details="pyproject missing")]
    text = pyproject_path.read_text(encoding="utf-8")
    has_fastagent = 'fastagent = "fastagent.cli.main:run"' in text
    return [
        ReleaseCheck(
            name="pyproject-scripts",
            passed=has_fastagent,
            severity="error",
            details="fastagent script found" if has_fastagent else "missing fastagent entrypoint script",
        )
    ]


def _check_tests_presence(project_path: Path) -> list[ReleaseCheck]:
    tests_path = project_path / "tests"
    if not tests_path.exists():
        return [ReleaseCheck(name="tests-presence", passed=False, severity="warning", details="tests directory missing")]
    count = len(list(tests_path.glob("test_*.py")))
    return [
        ReleaseCheck(
            name="tests-presence",
            passed=count > 0,
            severity="warning",
            details=f"{count} test files",
        )
    ]


def _check_docs_presence(project_path: Path) -> list[ReleaseCheck]:
    docs = [
        project_path / "docs" / "quickstart.md",
        project_path / "docs" / "architecture.md",
    ]
    missing = [str(item.relative_to(project_path)) for item in docs if not item.exists()]
    return [
        ReleaseCheck(
            name="docs-core",
            passed=not missing,
            severity="warning",
            details="all core docs present" if not missing else f"missing: {', '.join(missing)}",
        )
    ]


def _run_pytest(project_path: Path) -> ReleaseCheck:
    cmd = [sys.executable, "-m", "pytest", "-q"]
    completed = subprocess.run(cmd, cwd=str(project_path), capture_output=True, text=True)
    tail = (completed.stdout or completed.stderr or "").strip()
    if len(tail) > 300:
        tail = tail[-300:]
    return ReleaseCheck(
        name="pytest",
        passed=completed.returncode == 0,
        severity="error",
        details=f"return_code={completed.returncode}; tail={tail}",
    )


def summarize_release_checks(checks: list[ReleaseCheck]) -> dict:
    errors = [item for item in checks if item.severity == "error" and not item.passed]
    warnings = [item for item in checks if item.severity == "warning" and not item.passed]
    return {
        "ok": not errors,
        "errors": [item.to_dict() for item in errors],
        "warnings": [item.to_dict() for item in warnings],
        "checks": [item.to_dict() for item in checks],
    }


def write_release_report(path: Path, summary: dict) -> None:
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _extract_pyproject_version(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("version ="):
            parts = stripped.split("=", 1)
            if len(parts) != 2:
                continue
            return parts[1].strip().strip('"').strip("'")
    return ""


def _extract_init_version(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("__version__"):
            parts = stripped.split("=", 1)
            if len(parts) != 2:
                continue
            return parts[1].strip().strip('"').strip("'")
    return ""
