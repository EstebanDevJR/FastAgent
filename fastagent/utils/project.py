from pathlib import Path


def is_fastagent_project(project_path: Path) -> bool:
    return (project_path / "app" / "main.py").exists() and (project_path / "requirements.txt").exists()


def plugin_manifest_path(project_path: Path) -> Path:
    return project_path / "fastagent.plugins.json"


def ensure_project(project_path: Path) -> None:
    if not is_fastagent_project(project_path):
        raise ValueError("This does not look like a FastAgent project (missing app/main.py or requirements.txt)")