def agent_pattern_hint(project_type: str) -> str:
    mapping = {
        "chat": "Single conversational agent",
        "tool-agent": "Agent with tool execution",
        "rag": "Retriever-augmented generation",
        "multi-agent": "Planner/Worker/Reviewer",
    }
    return mapping.get(project_type, "Custom agent architecture")
