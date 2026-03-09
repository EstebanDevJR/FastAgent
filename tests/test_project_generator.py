from pathlib import Path

from fastagent.generators.project_generator import generate_project
from fastagent.utils.config import ProjectConfig


def test_generate_project_with_new_structure(tmp_path: Path) -> None:
    config = ProjectConfig(
        project_name="demo",
        project_type="rag",
        description="RAG agent for docs",
        tools=["contract_parser"],
        vector_db="Qdrant",
        memory_type="hybrid",
        evaluation_enabled=True,
        tracing="LangSmith",
    )
    target = tmp_path / "demo"
    generate_project(config=config, target_dir=target)

    assert (target / "app" / "main.py").exists()
    assert (target / "app" / "api" / "routes.py").exists()
    assert (target / "app" / "services" / "agent_service.py").exists()
    assert (target / "app" / "rag" / "retriever.py").exists()
    assert (target / "app" / "plugins" / "loader.py").exists()
    assert (target / "app" / "models" / "router.py").exists()
    assert (target / "docker" / "Dockerfile").exists()
    assert (target / "scripts" / "doctor.ps1").exists()
    assert (target / "scripts" / "bench.ps1").exists()
    assert (target / "fastagent.plugins.json").exists()
    assert not any("__pycache__" in str(path) for path in target.rglob("*"))
