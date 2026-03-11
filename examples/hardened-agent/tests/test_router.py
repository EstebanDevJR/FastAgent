from app.models.router import ModelRouter


def test_router_selects_provider() -> None:
    router = ModelRouter(mode="balanced", providers=["OpenAI", "Meta AI"])
    selected = router.select_provider()
    assert selected in {"OpenAI", "Meta AI"}


def test_router_fallback_provider() -> None:
    router = ModelRouter(mode="quality", providers=["OpenAI", "Meta AI"])
    fallback = router.fallback_provider("OpenAI")
    assert fallback == "Meta AI"
