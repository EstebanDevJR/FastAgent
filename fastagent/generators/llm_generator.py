def llm_provider_hint(provider: str) -> str:
    normalized = (provider or "").lower()
    if normalized == "openai":
        return "Set OPENAI_API_KEY in .env"
    if normalized == "anthropic":
        return "Set ANTHROPIC_API_KEY in .env"
    if normalized == "google deepmind":
        return "Set GOOGLE_API_KEY in .env"
    if normalized == "meta ai":
        return "Set META_API_KEY in .env"
    return "Set provider credentials in .env"
