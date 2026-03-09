import typer

from fastagent.cli.commands.add_plugin import add_plugin
from fastagent.cli.commands.add_agent import add_agent
from fastagent.cli.commands.add_tool import add_tool
from fastagent.cli.commands.bench import run_bench
from fastagent.cli.commands.create import create_project
from fastagent.cli.commands.doctor import run_doctor
from fastagent.cli.commands.eval import eval_project
from fastagent.cli.commands.plugins import disable_plugin, enable_plugin, list_plugins
from fastagent.cli.commands.redteam import generate_redteam
from fastagent.cli.commands.remove_plugin import remove_plugin_cmd
from fastagent.cli.commands.run import run_project

app = typer.Typer(
    no_args_is_help=True,
    help="FastAgent: AI Agent Backend Framework for FastAPI.",
)

app.command("create", help="Create a new FastAgent backend project.")(create_project)
app.command("new", help="Alias for create.")(create_project)
app.command("run", help="Run a generated FastAgent project.")(run_project)
app.command("eval", help="Evaluate agent outputs from a dataset.")(eval_project)
app.command("add-tool", help="Add a tool plugin to an existing project.")(add_tool)
app.command("add-agent", help="Add an agent module to an existing project.")(add_agent)
app.command("doctor", help="Run FastAgent environment diagnostics.")(run_doctor)
app.command("bench", help="Benchmark a running FastAgent API endpoint.")(run_bench)
app.command("plugins", help="List configured plugins in a project.")(list_plugins)
app.command("enable-plugin", help="Enable a configured plugin.")(enable_plugin)
app.command("disable-plugin", help="Disable a configured plugin.")(disable_plugin)
app.command("add-plugin", help="Add or update a plugin in project manifest.")(add_plugin)
app.command("remove-plugin", help="Remove a plugin from project manifest.")(remove_plugin_cmd)
app.command("redteam", help="Generate synthetic red-team evaluation cases.")(generate_redteam)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
