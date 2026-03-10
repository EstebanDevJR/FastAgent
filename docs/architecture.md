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
- Reproducible LLM-as-judge scoring (`fastagent eval --judge`)
- Canary quality guard + rollback signal (`fastagent canary-check`)
- Shadow traffic canary mode (`fastagent canary-shadow`) for baseline vs candidate endpoints
- Adaptive phased rollout controller (`fastagent rollout-controller --adaptive`) with persistent state
- Rollout traffic apply for Argo/Gateway (`fastagent rollout-apply`)
- End-to-end autopilot progressive delivery (`fastagent autopilot`)
- Signed deployment webhook automation with environment policy (`dev|staging|prod`)
- Human-in-the-loop approval gate (`fastagent autopilot --approval-gate`) with request lifecycle commands
- Approval SLA (`expires_at`) with auto-escalation notifications (Slack/Teams/generic webhook)
- Synthetic Red Team dataset generator (`fastagent redteam`)
- Trace replay harness for regression checks (`fastagent trace-replay`)
- Model Router in generated apps (quality/latency/cost routing + fallback)
- Plugin manifest and runtime plugin loader
- Registry-based plugin installer with SHA256 + Ed25519 verification and trust policy
- Policy engine with default deny rules (`app/policy/policies.json`)
- Multi-agent orchestrator with typed contracts and worker retries
- RAG v2 (chunking, dedupe, hybrid retrieval, reranker)
- Sandboxed plugin runtime (`app/plugins/sandbox.py`) with subprocess isolation
- Per-plugin sandbox profiles (`strict|balanced|off`) and signed plugin audit log
- `fastagent verify-audit` to validate audit-log integrity in CI
- Signed rollback webhook trigger (`fastagent rollback-webhook`) for deployment automation
- Runtime cost guardrails (session/global budget + block/alert)

Generated structure:

- `app/main.py`
- `app/api/routes.py`
- `app/agents/main_agent.py`
- `app/agents/contracts.py`
- `app/agents/orchestrator.py`
- `app/tools/tools.py`
- `app/memory/memory.py`
- `app/rag/retriever.py`
- `app/rag/chunker.py`
- `app/rag/hybrid.py`
- `app/rag/reranker.py`
- `app/models/llm.py`
- `app/models/cost_guard.py`
- `app/schemas/request.py`
- `app/config/settings.py`
- `app/services/agent_service.py`
- `app/evaluation/evaluator.py`
- `app/observability/tracing.py`
- `app/policy/engine.py`
- `app/plugins/loader.py`
- `app/plugins/sandbox.py`
- `fastagent.plugins.json`
- `tests/`
- `docker/`
- `scripts/`
