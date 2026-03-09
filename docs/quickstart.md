# Quickstart

```bash
pip install -e .
fastagent create my-agent
cd my-agent
pip install -r requirements.txt
uvicorn app.main:app --reload
```

With Architect providers:

```bash
fastagent create legal-agent --architect-provider local --yes --description "AI for legal contracts"
fastagent create legal-agent-openai --architect-provider openai --architect-model gpt-4o-mini --yes --description "AI for legal contracts"
fastagent create legal-agent-ollama --architect-provider ollama --architect-model llama3.1 --yes --description "AI for legal contracts"
```

Hardening options:

```bash
fastagent create legal-agent \
  --architect-openai-mode auto \
  --architect-timeout 20 \
  --architect-retries 2 \
  --architect-backoff 0.5 \
  --architect-cache \
  --architect-cache-ttl 3600
```

Run with Docker:

```bash
fastagent run --project-path . --docker
fastagent run --project-path . --docker --detach
```

Optional:

```bash
fastagent add-tool contract_parser --project-path .
fastagent add-agent reviewer --project-path .
fastagent eval --dataset examples/eval_dataset.sample.jsonl
fastagent eval --config fastagent.eval.json --gate
fastagent doctor --project-path .
fastagent bench --base-url http://127.0.0.1:8000 --endpoint /chat
fastagent redteam --output redteam.jsonl --count 100 --domain "legal agents"
fastagent plugins --project-path .
fastagent add-plugin legal_tools --project-path . --source local
```
