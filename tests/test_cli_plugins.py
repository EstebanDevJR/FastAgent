from pathlib import Path

from typer.testing import CliRunner

from fastagent.cli.main import app

runner = CliRunner()


def _init_fake_project(path: Path) -> None:
    (path / "app").mkdir(parents=True, exist_ok=True)
    (path / "app" / "main.py").write_text("app = None\n", encoding="utf-8")
    (path / "requirements.txt").write_text("fastapi\n", encoding="utf-8")


def test_plugins_no_plugins_message(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)
    result = runner.invoke(app, ["plugins", "--project-path", str(tmp_path)])
    assert result.exit_code == 0
    assert "No plugins configured" in result.stdout


def test_add_plugin_then_list(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)
    add_result = runner.invoke(
        app,
        ["add-plugin", "my_plugin", "--project-path", str(tmp_path), "--source", "local"],
    )
    assert add_result.exit_code == 0
    assert "Plugin upserted" in add_result.stdout

    list_result = runner.invoke(app, ["plugins", "--project-path", str(tmp_path)])
    assert list_result.exit_code == 0
    assert "my_plugin" in list_result.stdout
    assert "balanced" in list_result.stdout


def test_add_plugin_custom_profile(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)
    add_result = runner.invoke(
        app,
        [
            "add-plugin",
            "secure_plugin",
            "--project-path",
            str(tmp_path),
            "--source",
            "local",
            "--sandbox-profile",
            "strict",
        ],
    )
    assert add_result.exit_code == 0

    list_result = runner.invoke(app, ["plugins", "--project-path", str(tmp_path)])
    assert list_result.exit_code == 0
    assert "strict" in list_result.stdout


def test_add_plugin_invalid_profile(tmp_path: Path) -> None:
    _init_fake_project(tmp_path)
    result = runner.invoke(
        app,
        [
            "add-plugin",
            "bad_profile",
            "--project-path",
            str(tmp_path),
            "--sandbox-profile",
            "ultra",
        ],
    )
    assert result.exit_code != 0
    assert "--sandbox-profile must be one of" in result.stdout
