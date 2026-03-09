# FastAgent Architecture

FastAgent CLI flow:

1. `fastagent create`
2. Project Architect recommendation (`local`, `openai`, or `ollama`)
3. Architecture generator
4. Project scaffold

Project Architect hardening:

- strict JSON schema keys validation
- canonicalization for provider outputs
- retries with exponential backoff
- OpenAI Responses API + Chat Completions fallback
- architect cache with TTL
- automatic fallback to local heuristic engine

Runtime and quality innovations:

- Eval-as-Code + CI Gate via config JSON thresholds
- Synthetic Red Team dataset generator (`fastagent redteam`)
- Model Router in generated apps (quality/latency/cost routing + fallback)
- Plugin manifest and runtime plugin loader

Generated structure:

- `app/main.py`
- `app/api/routes.py`
- `app/agents/main_agent.py`
- `app/tools/tools.py`
- `app/memory/memory.py`
- `app/rag/retriever.py`
- `app/models/llm.py`
- `app/schemas/request.py`
- `app/config/settings.py`
- `app/services/agent_service.py`
- `app/evaluation/evaluator.py`
- `app/observability/tracing.py`
- `app/plugins/loader.py`
- `fastagent.plugins.json`
- `tests/`
- `docker/`
- `scripts/`
