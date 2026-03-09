from pathlib import Path
import shutil

from jinja2 import Environment, FileSystemLoader

from fastagent.generators.agent_generator import agent_pattern_hint
from fastagent.generators.llm_generator import llm_provider_hint
from fastagent.generators.rag_generator import rag_hint
from fastagent.utils.config import ProjectConfig
from fastagent.utils.file_utils import ensure_directory, write_text


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "agent_backend_template"


def _build_context(config: ProjectConfig) -> dict:
    context = config.to_template_context()
    context.update(
        {
            "agent_pattern_hint": agent_pattern_hint(config.project_type),
            "llm_provider_hint": llm_provider_hint(config.llm_provider),
            "rag_hint": rag_hint(config.vector_db),
        }
    )
    return context


def _render_template_file(env: Environment, source_file: Path, rel_path: Path, target_dir: Path, context: dict) -> None:
    if source_file.suffix == ".j2":
        template = env.get_template(str(rel_path).replace("\\", "/"))
        rendered = template.render(**context)
        output_rel = rel_path.with_suffix("")
        write_text(target_dir / output_rel, rendered)
    else:
        ensure_directory((target_dir / rel_path).parent)
        shutil.copy2(source_file, target_dir / rel_path)


def _should_skip_template_path(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def generate_project(config: ProjectConfig, target_dir: Path) -> None:
    ensure_directory(target_dir)
    context = _build_context(config)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    for source in TEMPLATE_DIR.rglob("*"):
        if source.is_dir() or _should_skip_template_path(source):
            continue
        rel_path = source.relative_to(TEMPLATE_DIR)
        _render_template_file(env, source, rel_path, target_dir, context)