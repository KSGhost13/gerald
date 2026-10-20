# QwenW specialist pack

GERALD stays the only workflow runtime. This pack adapts the six Markdown profiles from the original QwenW folder; it does **not** execute its prototype `main.py` or `run_engine.ps1`, launch another master brain, or poll an independent loop.

## Install and locate the files

The six portable profiles are included in `packs/qwenw/agents`, with content hashes in `packs/qwenw/manifest.json`. From a running checkout:

```powershell
.\.venv\Scripts\python.exe scripts\import-qwenw.py --install
```

Alternatively click **QwenW toolbox** (wrench icon) → **Import staged profiles**. Installation is idempotent: existing profiles are retained; missing profiles are restored. Existing agents, master/session binding, and routes are not replaced. Each new specialist is connected directly from GERALD, just like a manually forged worker. No tasks run on import. Model/provider, directive, graph position, and permitted tool selections can be configured per worker.

To preserve a specific original folder first:

```powershell
.\.venv\Scripts\python.exe scripts\import-qwenw.py --source "C:\path\to\QwenW" --install
```

This copies every regular source file and directory into ignored `data/imports/qwenw/source`, preserving the originals. Its manifest hashes every copied file; changed bytes are rejected on install. The managed snapshot is immutable, not a live sync of Desktop edits. A local staged snapshot takes precedence over bundled profiles. Do not remove/restage one while work is active. Links/junctions, traversal, more than 256 files/16 MiB total, and individual files over 1 MiB are rejected. Imported executables are archives, never plugin code. Empty prototype state files are preserved but not parsed as JSON.

Runtime canvas/drafts are kept in GERALD's SQLite database. `data/workspace/qwenw/project_canvas.json` is a generated compatibility mirror, not a second authoritative database. Use the dashboard, MCP or REST API to edit shared state; direct mirror edits are not ingested. Generated files go under `data/workspace/qwenw/generated/<mission-id>/`; outreach `.txt` backups go under `data/workspace/qwenw/outreach/`. Runtime data, local source snapshots, model catalogues and credentials are not committed.

## Profile capabilities

| Profile | Writes through the adapter | Boundaries |
| --- | --- | --- |
| Client acquisitions | `sales_insights`; optional outreach draft | Draft always starts `PENDING_HUMAN_APPROVAL`; plaintext backup; no sending transport |
| Researcher | `research_metrics` | Uses supplied evidence; no scraper was included; must not invent research |
| Planner | `architectural_blueprint` | No code-write permission; cannot mark its own plan human-verified |
| UI designer | `design_tokens` | No code writes; design changes invalidate human verification |
| Coder | `engineering_manifest`; proposed generated files | Blocked before model generation unless current architecture/design are human-verified |
| Communicator | Public answer only | Summarizes the current task/canvas, not an autonomous polling daemon |

All profiles can receive shared project context. Customer draft/history context is injected only into Client Acquisitions. This is a single-user project workspace, not per-agent confidential storage. The adapter enforces the profile's writable section regardless of instructions in a prompt or returned JSON.

### Suggested workflow

1. Enter the brief, target niche and supplied source evidence under `sales_insights` in the toolbox canvas editor. Save it.
2. Use **Researcher** for evidence analysis, **Planner** for the architecture, and **UI Designer** for tokens/layout specs. Select each specialist directly in Command Uplink, or have the existing bound master chat explicitly assign a task. Context from a Codex conversation must be passed in the task/canvas; it is not silently extracted from other chats.
3. Review `architectural_blueprint` and `design_tokens`. Click **Verify reviewed architecture & design** only after reviewing them. Verification is bound to their content digest. Edits to either invalidate it; stale editor/model writes are rejected rather than overwriting newer data.
4. Assign **Coder**, then **Communicator**. Coder outputs are saved as create-only artifacts; the adapter never runs generated code. Review/test them separately before adopting them.
5. For outreach, assign **Client Acquisitions** with a drafting brief. Review the resulting draft and optionally mark it **Approved for manual use**. This does not send email, register a webhook, or connect an inbox. Send manually through your chosen email application only after your own review.

Do not connect a single unattended chain through the coder review gate and expect automatic human approval. You can build DAG routes in the matrix, but a locked coder task fails with a visible explanation until reviewed. Directly connected master targets are available for explicit assignments; there is no fan-in/barrier scheduler added by this pack.

## How tools work

The pack adds `qwen_canvas_read`, `qwen_canvas_write`, and `qwen_outreach_draft` to profile configuration. Existing `workspace_read`, `workspace_write`, and `system_metrics` remain available according to profile permissions. The UI also documents the operator architecture review and coder artifact writer.

For consistent Ollama HTTP, Ollama CLI, Codex CLI (cloud/local), and Anthropic behavior, pack actions are **validated JSON proposals**, not native function calls:

```json
{
  "answer": "Public task result",
  "canvas": {"research_metrics": {"summary": "Evidence-backed findings"}},
  "files": [],
  "draft": null
}
```

`canvas` can contain only the profile's assigned section. Omit unchanged data. Coder `files` may contain up to 16 `{path, content}` objects, at most 64 KiB each; paths cannot escape the mission directory, use Windows device/stream names, or overwrite existing files. Only Client Acquisitions can propose `{to, subject, body}` in `draft`; malformed recipients, header newlines, and common credential/connection-string patterns are rejected. Secret scanning is a safeguard, not a guarantee—never put credentials into project briefs or email drafts.

The injected contract supersedes legacy absolute paths and polling instructions. QwenW Codex subprocesses are read-only with shell, browser, code-mode host, image, web search and subagent features disabled; they propose artifacts through the adapter instead of executing their own tools or calling the review API. Non-pack Codex workers retain the existing workspace tool behavior. Local process access to the dashboard is not strong authentication; keep GERALD on loopback and do not expose it to untrusted users/processes.

Malformed or out-of-scope outputs fail the mission without applying proposed canvas updates. An architecture/design change during coder generation invalidates its proposal, even if a newer revision was subsequently re-verified. Saved artifacts should still be reviewed after interrupted disk operations; file writes and SQLite are not one filesystem/database transaction.

## Codex desktop and CLI

The bridge now exposes thirteen tools, adding `gerald_qwenw_state` and `gerald_qwenw_canvas`. Reload Codex to discover new MCP tools. No reload is required for REST/CLI operation:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/api/packs/qwenw
```

Canvas updates use `PUT /api/packs/qwenw/canvas` with `section`, `value`, and the current `expected_revision`. Human verification is `POST /api/packs/qwenw/verify`; draft review is `POST /api/packs/qwenw/drafts/<id>/approve`, also revision-checked. No email-sending endpoint exists. The existing session inbox/claim/respond protocol is unchanged.

## Select a model per agent / use a Codex subscription

1. Confirm `codex login status` says **Logged in using ChatGPT**. If not, run `codex login` in your terminal and complete the normal sign-in flow. GERALD does not collect, copy, or expose authentication tokens.
2. In **Active units**, open an agent's configure button. Choose **Brain / Provider → Codex · Cloud sign-in**.
3. Select a specific model from the real **Model** dropdown, or **Provider default**. **Custom model ID…** allows an exact model not in the cached catalogue. Save. Each agent stores its own provider/model; the cards display the configured model.
4. Enable **Cloud Apex mode** before running cloud workers. **Local Fallback mode** intentionally routes configured cloud workers to the local Ollama default. A cloud failure also falls back to local Ollama and is reported in the activity log; inspect the effective provider rather than assuming cloud ran.

The dropdown uses installed Ollama tags for the selected server, or visible entries from Codex's non-secret `models_cache.json` for Codex cloud. The catalogue can be stale and does not guarantee entitlement; availability is checked by the CLI at execution. Use **Integrations → Refresh discovery** after installations/sign-in/catalogue updates. Anthropic uses an explicit custom model ID and its own API credential. If GERALD is bound to an existing Codex chat, that master follows the model selected in the chat; dashboard model selection is disabled for the session provider.

ChatGPT sign-in provides supported Codex subscription access, subject to your plan/workspace limits. It does not turn the subscription into general-purpose API credits or allow every OpenAI API model. API-key authentication is separate usage-based billing. See [OpenAI authentication documentation](https://learn.chatgpt.com/docs/auth).

## Verification

Run the backend suite and frontend build normally. `scripts/verify-qwenw.py` additionally runs real short Ollama and Codex cloud generations through the imported Communicator adapter, requires an idle dashboard and ChatGPT CLI sign-in, restores the starting mode/provider/model, and writes ignored `data/qwenw-verification.json`. It uses supplied test data and does not approve architecture, create/send email, or change the canvas. This check does not verify all models or every provider/profile combination.
