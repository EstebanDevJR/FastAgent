# FastAgent

AI Agent Backend Framework for FastAPI.

FastAgent is a CLI to scaffold production-ready AI agent backends with FastAPI.

## What it generates

- Agent layer (`chat`, `rag`, `tool-agent`, `multi-agent`)
- Multi-agent orchestration contracts + retries
- Tool system (plugins + built-ins)
- Sandboxed plugin execution (timeout + memory controls)
- Memory strategies (conversation/vector/hybrid)
- RAG retriever module
- Evaluation module
- Tracing/observability hooks
- Built-in policy engine and guardrails
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
fastagent eval --dataset examples/eval_dataset.sample.jsonl --judge --judge-seed 42
fastagent eval --config fastagent.eval.json --gate
fastagent canary-check --baseline-report baseline_eval.json --candidate-report candidate_eval.json
fastagent canary-shadow --simulate --simulate-count 30 --simulate-degradation 0.12
fastagent rollout-controller --adaptive --canary-report canary_report.json --shadow-report shadow_report.json
fastagent rollout-apply --decision-report rollout_decision.json --provider argo --resource legal-agent-rollout
fastagent autopilot --baseline-report baseline_eval.json --candidate-report candidate_eval.json --shadow-mode simulate --apply-provider argo --apply-resource legal-agent-rollout
fastagent autopilot --baseline-report baseline_eval.json --candidate-report candidate_eval.json --webhook --webhook-environment staging --webhook-mode auto
fastagent doctor --project-path <path>
fastagent bench --base-url http://127.0.0.1:8000 --endpoint /chat
fastagent init-ci --project-path <path>
fastagent redteam --output redteam.jsonl --count 100 --domain "legal agents"
fastagent release-ready --project-path . --run-tests
fastagent trace-replay --trace-file logs/traces.jsonl --base-url http://127.0.0.1:8000
fastagent validate-artifacts --artifact eval_report:eval_report.json --artifact canary_report:canary_report.json
powershell -ExecutionPolicy Bypass -File scripts/e2e.ps1
fastagent verify-audit --log-file logs/plugin_audit.jsonl
fastagent rollback-webhook --url https://deploy.example/hooks/rollback --secret $FASTAGENT_ROLLBACK_WEBHOOK_SECRET --dry-run
fastagent approval-list --state-file rollout.approvals.json
fastagent approval-resolve --state-file rollout.approvals.json --request-id <id> --decision approve --approver ops-lead
fastagent add-tool <tool-name> --project-path <path>
fastagent add-agent <agent-name> --project-path <path>
fastagent plugins --project-path <path>
fastagent install-plugin <plugin-name> --project-path <path> --registry <url-or-file>
fastagent init-trust --project-path <path>
fastagent generate-signing-key --output-dir .
fastagent sign-plugin plugins/my_tool.py --private-key fastagent_plugin_signing.private.pem --key-id team-key-1
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
fastagent eval --dataset examples/eval_dataset.sample.jsonl --judge --judge-seed 42
```

## Canary Rollout Check

Compare baseline vs candidate quality before rollout:

```bash
fastagent canary-check \
  --baseline-report baseline_eval.json \
  --candidate-report candidate_eval.json
```

Shadow traffic gate before full rollout:

```bash
fastagent canary-shadow \
  --baseline-url https://api-baseline.example.com \
  --candidate-url https://api-candidate.example.com \
  --sample-file examples/shadow_samples.sample.jsonl
```

Automate phased rollout decision (5/25/50/100 by default):

```bash
fastagent rollout-controller \
  --state-file rollout.state.json \
  --adaptive \
  --canary-report canary_report.json \
  --shadow-report shadow_report.json \
  --deployment-id "$GIT_SHA"
```

Apply traffic weight to platform (Argo/Gateway):

```bash
fastagent rollout-apply \
  --decision-report rollout_decision.json \
  --provider argo \
  --resource legal-agent-rollout \
  --namespace default
```

Single-command progressive delivery orchestration:

```bash
fastagent autopilot \
  --baseline-report baseline_eval.json \
  --candidate-report candidate_eval.json \
  --shadow-mode simulate \
  --apply-provider argo \
  --apply-resource legal-agent-rollout \
  --output-json autopilot_report.json
```

Signed deployment webhook with environment policy (`dev|staging|prod`):

```bash
export FASTAGENT_DEPLOY_WEBHOOK_URL="https://deploy.example/hooks/events"
export FASTAGENT_DEPLOY_WEBHOOK_SECRET="super-secret"

fastagent autopilot \
  --baseline-report baseline_eval.json \
  --candidate-report candidate_eval.json \
  --webhook \
  --webhook-environment prod \
  --webhook-mode auto \
  --output-json autopilot_report.json
```

Human-in-the-loop gate for `rollout_hold`:

```bash
fastagent autopilot \
  --baseline-report baseline_eval.json \
  --candidate-report candidate_eval.json \
  --approval-gate \
  --approval-state-file rollout.approvals.json \
  --approval-ttl-minutes 60 \
  --webhook-environment prod \
  --output-json autopilot_pending.json
# exits with code 5 when approval is required

fastagent approval-list --state-file rollout.approvals.json
fastagent approval-resolve --state-file rollout.approvals.json --request-id <id> --decision approve --approver ops-lead

fastagent autopilot \
  --baseline-report baseline_eval.json \
  --candidate-report candidate_eval.json \
  --approval-gate \
  --approval-state-file rollout.approvals.json \
  --approval-request-id <id> \
  --webhook-environment prod \
  --output-json autopilot_approved.json
```

Escalation when SLA expires (Slack/Teams/generic webhook):

```bash
fastagent autopilot \
  --baseline-report baseline_eval.json \
  --candidate-report candidate_eval.json \
  --approval-gate \
  --approval-state-file rollout.approvals.json \
  --approval-request-id <id> \
  --approval-escalation-urls "https://hooks.slack.com/services/XXX/YYY/ZZZ,https://outlook.office.com/webhook/ABC/DEF" \
  --approval-escalation-mode dry-run \
  --approval-escalation-dedupe \
  --webhook-environment prod \
  --output-json autopilot_expired.json
# exit code 7 => approval expired
```

Validate pipeline artifacts before promotion:

```bash
fastagent validate-artifacts \
  --artifact eval_report:eval_report.json \
  --artifact canary_report:canary_report.json \
  --artifact rollout_decision:rollout_decision.json \
  --artifact autopilot_report:autopilot_report.json
```

Release readiness checklist:

```bash
fastagent release-ready --project-path . --run-tests --output-json release_ready.json
```

One-command local end-to-end smoke:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/e2e.ps1
# Optional: -SkipRepoTests -SkipProjectInstall -CleanupWorkDir
```

Optional policy override file:

```json
{
  "prod": {
    "promote_max_risk": 0.3,
    "require_apply_success_for_promote": true,
    "webhook_dry_run_default": false,
    "send_events": ["rollback_requested", "promotion_requested", "rollout_hold"]
  }
}
```

## Synthetic Red Team

Generate adversarial test sets quickly:

```bash
fastagent redteam --output redteam.jsonl --count 200 --domain "healthcare assistants"
```

## Trace Replay

Replay prior production traces against a local/staging API:

```bash
fastagent trace-replay \
  --trace-file logs/traces.jsonl \
  --event chat_request \
  --base-url http://127.0.0.1:8000 \
  --endpoint /chat
```

## CI Bootstrap

Initialize a GitHub Actions eval gate workflow in an existing FastAgent project:

```bash
fastagent init-ci --project-path .
```

## Plugin Registry + Integrity Checks

Install signed plugins from a local or remote registry:

```bash
fastagent install-plugin currency_tool \
  --project-path . \
  --registry examples/plugin_registry.sample.json \
  --sandbox-profile strict
```

FastAgent verifies plugin SHA256 and Ed25519 signature by default (`--allow-unsigned` to bypass for specific cases).
Each plugin can run with profile `strict|balanced|off` and execution is audit-logged with signature.

Verify plugin audit integrity:

```bash
fastagent verify-audit --log-file logs/plugin_audit.jsonl --secret "$PLUGIN_AUDIT_SECRET"
```

Initialize trust policy and signing keys:

```bash
fastagent init-trust --project-path . --allowed-registry fastagent-local-sample --trusted-key-id sample-key-1
fastagent generate-signing-key --output-dir . --name sample_signing
fastagent sign-plugin examples/plugins/currency_tool.py \
  --private-key sample_signing.private.pem \
  --key-id sample-key-1 \
  --include-key
```

Reference policy example: `examples/fastagent.trust.sample.json`.

## License

MIT
