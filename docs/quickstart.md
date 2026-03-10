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
fastagent eval --dataset examples/eval_dataset.sample.jsonl --judge --judge-seed 42
fastagent eval --config fastagent.eval.json --gate
fastagent canary-check --baseline-report baseline_eval.json --candidate-report candidate_eval.json
fastagent canary-shadow --simulate --simulate-count 30 --simulate-degradation 0.12
fastagent rollout-controller --adaptive --canary-report canary_report.json --shadow-report shadow_report.json
fastagent rollout-apply --decision-report rollout_decision.json --provider argo --resource my-agent-rollout
fastagent autopilot --baseline-report baseline_eval.json --candidate-report candidate_eval.json --shadow-mode simulate --apply-provider argo --apply-resource my-agent-rollout
fastagent autopilot --baseline-report baseline_eval.json --candidate-report candidate_eval.json --webhook --webhook-environment dev --webhook-mode auto
fastagent autopilot --baseline-report baseline_eval.json --candidate-report candidate_eval.json --approval-gate --approval-state-file rollout.approvals.json --webhook-environment prod
fastagent approval-list --state-file rollout.approvals.json
fastagent approval-resolve --state-file rollout.approvals.json --request-id <id> --decision approve --approver ops-lead
fastagent autopilot --baseline-report baseline_eval.json --candidate-report candidate_eval.json --approval-gate --approval-state-file rollout.approvals.json --approval-request-id <id> --approval-escalation-url "https://hooks.slack.com/services/XXX/YYY/ZZZ" --approval-escalation-mode dry-run --webhook-environment prod
fastagent doctor --project-path .
fastagent bench --base-url http://127.0.0.1:8000 --endpoint /chat
fastagent redteam --output redteam.jsonl --count 100 --domain "legal agents"
fastagent plugins --project-path .
fastagent add-plugin legal_tools --project-path . --source local
fastagent install-plugin currency_tool --project-path . --registry examples/plugin_registry.sample.json --sandbox-profile strict
fastagent init-trust --project-path . --allowed-registry fastagent-local-sample --trusted-key-id sample-key-1
fastagent trace-replay --trace-file logs/traces.jsonl --base-url http://127.0.0.1:8000
fastagent verify-audit --log-file logs/plugin_audit.jsonl --allow-missing
fastagent rollback-webhook --url https://deploy.example/hooks/rollback --secret "$FASTAGENT_ROLLBACK_WEBHOOK_SECRET" --dry-run
fastagent init-ci --project-path .
```
