from pathlib import Path

from typer.testing import CliRunner

from fastagent.cli.main import app


runner = CliRunner()


def _write_minimal_project(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "fastagent" / "cli").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)

    (root / "README.md").write_text("# x\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (root / "docs" / "quickstart.md").write_text("# q\n", encoding="utf-8")
    (root / "docs" / "architecture.md").write_text("# a\n", encoding="utf-8")
    (root / "fastagent" / "__init__.py").write_text('__version__ = "1.2.3"\n', encoding="utf-8")
    (root / "fastagent" / "cli" / "main.py").write_text("app = None\n", encoding="utf-8")
    (root / "tests" / "test_sample.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "fastagent"',
                'version = "1.2.3"',
                "[project.scripts]",
                'fastagent = "fastagent.cli.main:run"',
            ]
        ),
        encoding="utf-8",
    )


def test_release_ready_passes_for_minimal_project(tmp_path: Path) -> None:
    _write_minimal_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "release-ready",
            "--project-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0


def test_release_ready_fails_when_required_file_missing(tmp_path: Path) -> None:
    _write_minimal_project(tmp_path)
    (tmp_path / "LICENSE").unlink()
    result = runner.invoke(
        app,
        [
            "release-ready",
            "--project-path",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 2
