# Private business launch desk

The **Business launch** tab reads a small local configuration and offers downloads of an explicit set of launch documents. It is a read-only preparation desk, **not a CRM/email sender or always-on support service**. No additional Python/npm packages are needed.

## Configure locally

Create `data/workspace/business-launch/desk.json` (ignored by Git):

```json
{
  "name": "Example Studio",
  "markets": ["Your actual service area"],
  "email": "owner@example.com",
  "phase": "Internal preparation — not accepting commitments",
  "budget": "$0 additional spending authorized",
  "next_actions": ["Review scope, capacity and legal readiness"]
}
```

Only validated display fields are returned by `GET /api/business`; extra configuration fields are never exposed. Do not store credentials in this file. The existing localhost Host/Origin guard applies. This is still a single-user local application, not authentication against other local processes.

Supported local documents: `START-HERE.md`, `LAUNCH-PLAN.md`, `SERVICE-PLAYBOOK.md`, `EMAIL-SETUP.md`, `TEMPLATES.md`, `SOURCES.md`, `prospects.csv`, `TEAM-RESULTS.md`. The document endpoint permits only these fixed names, serves plain-text attachments and rejects path/link escapes. Other runtime files, snapshots and arbitrary workspace files are not downloadable through it. Keep client-sensitive material and credentials out of these display documents.

Refresh the tab after updating files. A Gmail link opens the first account in that browser; verify the selected address. Displaying an email address or having a browser session does **not** grant agents OAuth/IMAP/SMTP access. Mail transport, scopes, signup terms, exact recipient/content approval and support staffing are separate decisions. No background mail polling or sending is installed.

## Bounded internal planning run

An operator may prepare `batch.json` in the same ignored directory, then run:

```powershell
.\.venv\Scripts\python.exe scripts\run-launch.py
```

The runner requires a running local dashboard, no bound session brain, an idle team, existing Ollama model, and read-only participating workers. It does not install/configure agents or fetch models. Example batch shape:

```json
{
  "model": "your-installed-model",
  "brief": "Internal planning only; no external side effects or approval authority.",
  "active_ids": ["gerald", "existing-worker-id"],
  "stages": [{
    "key": "strategy",
    "agent_id": "existing-worker-id",
    "task": "Draft a short offer experiment and identify owner decisions.",
    "evidence": "Supplied facts only; no independent browsing capability.",
    "review_previous": false
  }]
}
```

Back up agents, mode, routes and canvas before configuring a new workflow. No other missions/graph editing or parallel runner should run during this operator-supervised batch. Each stage connects only one worker to the master, submits an orchestrator job and waits for a real terminal worker result. It saves a durable `run.json` ledger and `<stage>.md` AI drafts, then restores the prior routes when no work is active. It never calls a send, purchase, deployment, approval or chat-binding endpoint. Existing local providers and tool capabilities must still be reviewed by the operator; prompts are not a security boundary.

Completed stages are not replayed. A lost submission response, failure, interruption, missing result or timeout stops the run and requires reconciliation of the recorded job/marker before retrying. Do not clear the ledger to force a replay. For an active task, wait or explicitly abort through the dashboard; inspect `routing-recovery.json` before restoring routes. Follow actual job status, not the terminal merely exiting. Proposed actions in AI drafts are not owner approvals or evidence those actions occurred.

## Orchestrator safety

Model-master plans accept only `summary` and `tasks`, at most eight distinct, connected assignments with nonempty string tasks. Invalid plans fail closed, unavailable workers reject the entire batch before enqueue, and `tasks: []` is a legitimate review/summary stop. There is no implicit fan-out fallback. Ordinary non-master edges still route results, so remove peer edges for a staged supervised workflow. The master directive should use a smaller practical limit (one or two tasks for a local launch batch).

Ollama HTTP master calls use the plan JSON schema; read-only QwenW calls use a schema requiring empty canvas/files and null draft; writable QwenW calls request JSON mode, following [Ollama's structured-output interface](https://ollama.com/blog/structured-outputs). Runtime validation still applies: constrained syntax is not evidence of correctness or approval. Other providers must satisfy the same validated output contracts; there is no permissive text-to-actions fallback.

Coder architecture verification remains a separate human gate. Pausing a worker is process-local, so reapply pause after a server restart; an unverified architecture gate remains persistent. No agent should self-approve human review, marketing drafts or production release.

## Verify and deploy code updates

Run backend tests as described in README and `npm run build` in `frontend`. Restart the identity-checked managed server to load backend changes, then reload the dashboard. Private business identity, candidate research, contacts, snapshots, ledger and generated outputs belong under ignored `data/`, not the reusable source repository. Existing model/cloud/chat settings outside this dashboard are not modified.
