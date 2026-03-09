# FastAgent

AI Agent Backend Framework for FastAPI.

FastAgent is a CLI to scaffold production-ready AI agent backends with FastAPI.

## What it generates

- Agent layer (`chat`, `rag`, `tool-agent`, `multi-agent`)
- Tool system (plugins + built-ins)
- Memory strategies (conversation/vector/hybrid)
- RAG retriever module
- Evaluation module
- Tracing/observability hooks
- Docker-ready structure

## Install

```bash
pip install -e .
```

## Commands

```bash
fastagent create <project-name>
fastagent run --project-path <path>
fastagent run --project-path <path> --docker
fastagent eval --dataset examples/eval_dataset.sample.jsonl
fastagent eval --config fastagent.eval.json --gate
fastagent doctor --project-path <path>
fastagent bench --base-url http://127.0.0.1:8000 --endpoint /chat
fastagent redteam --output redteam.jsonl --count 100 --domain "legal agents"
fastagent add-tool <tool-name> --project-path <path>
fastagent add-agent <agent-name> --project-path <path>
fastagent plugins --project-path <path>
fastagent add-plugin <plugin-name> --project-path <path>
```

## Architect options

```bash
fastagent create legal-agent \
  --architect-provider openai \
  --architect-model gpt-4o-mini \
  --architect-openai-mode auto \
  --architect-timeout 20 \
  --architect-retries 2 \
  --architect-backoff 0.5 \
  --architect-cache \
  --architect-cache-ttl 3600
```

Architect providers:

- `local` (heuristic, default)
- `openai` (uses `OPENAI_API_KEY`)
- `ollama` (uses local Ollama HTTP API)

If provider calls fail or return invalid JSON schema, FastAgent falls back automatically to local heuristics.

## OpenAI Architect Engine

- `auto`: tries Responses API first, then Chat Completions fallback.
- `responses`: force Responses API.
- `chat`: force Chat Completions.

FastAgent also includes architect recommendation cache with TTL to reduce repeated remote calls.

## Eval-as-Code + CI Gate

Use an eval config file and fail CI automatically when quality drops:

```json
{
  "dataset": "examples/eval_dataset.sample.jsonl",
  "thresholds": {
    "accuracy_min": 0.8,
    "reasoning_quality_min": 0.8,
    "hallucinations_max": 0.3,
    "cost_max": 2.0
  },
  "report_path": "eval_report.json"
}
```

```bash
fastagent eval --config fastagent.eval.json --gate
```

## Synthetic Red Team

Generate adversarial test sets quickly:

```bash
fastagent redteam --output redteam.jsonl --count 200 --domain "healthcare assistants"
```

## License

MIT
