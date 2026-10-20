# Verified on this machine

## QwenW and per-agent model selection — October 20, 2026

- Final expanded backend suite: **32 passed**. TypeScript and Vite production build passed. Final narrow-window toolbox inspection at 390×844 confirmed 16px canvas input text and no horizontal page overflow.
- Installed all six original profiles without running the prototype engine, changing the master/session configuration, or replacing existing agents/routes. All ten source files were hash-preserved in ignored local storage; six portable profiles are bundled separately.
- Model dropdown inspected in the browser: installed Ollama tags and seven visible cached Codex choices appeared, and a specific cloud model survived Save configuration and reopening the form. Codex CLI reports ChatGPT sign-in; no credentials are read/exposed by discovery.
- Real imported Communicator tasks completed through Ollama HTTP (`ornith-1.5:9b`) and Codex CLI cloud (`gpt-6.1-sol`), with effective providers verified and no canvas edits or external messages. Results stay in ignored `data/qwenw-verification.json`. Other combinations/catalogue entries are not all live-tested.
- Official MCP client discovered thirteen tools, including QwenW state/canvas operations, and read live state successfully.
- Tests cover import hashing/idempotency, ignored engine code, scoped/stale canvas proposals, human architecture gating and invalidation, create-only artifacts/path restrictions, draft review/secret-pattern rejection, restart persistence, and safe model/auth discovery. These are not a complete security/WCAG audit.

## Readability update — October 20, 2026

- TypeScript check and production build passed; all 15 backend regression tests passed.
- Browser inspection at 1440×1000 and 390×844 confirmed 16px body/form typography, 48–50px command controls, and 44px agent action targets. Neither viewport had horizontal page overflow.
- Agent configuration dialog inspected at both widths: 16px inputs, wrapping single-column fields on narrow windows, and internal scrolling for long forms. No agent configuration or session binding was changed.
- Graph labels are enlarged and initial automatic fit is bounded to 85% zoom rather than shrinking the graph arbitrarily. Users can still pan and adjust zoom.
- These are targeted readability/layout checks, not a complete WCAG audit or performance benchmark.

- Python backend: the original 15 automated tests cover routing, lifecycle controls, cloud fallback, API/WebSocket behavior, local-only policy, parent/child process termination, persisted recovery, and the six existing-chat integration cases described below. The expanded QwenW suite is run alongside them.
- TypeScript check and Vite production build pass.
- Final npm audit reports zero known vulnerabilities.
- Actual generation works through Ollama HTTP, Ollama CLI, Codex CLI cloud (existing ChatGPT sign-in), and Codex CLI local with Qwen 2.5 Coder 14B. Results: `VERIFICATION.json`.
- Official MCP client initialized the stdio bridge and retrieved live dashboard state. The bridge now has thirteen tools, including four session tools and two QwenW tools. `codex mcp get gerald` confirms the installed registration.
- Dashboard inspected in the Codex browser; ATLAS was created using its forge form.
- Full GERALD → ATLAS → SCRIBE mission completed with zero errors. Results: `WORKFLOW-VERIFICATION.json`.

The session extension adds six tests for UI directive pickup without model generation, explicit worker routing and duplicate callback handling, wrong-chat/stale-claim rejection, pause/disconnect, persisted recovery, and an API round trip. A real directive was submitted through the dashboard and answered in the bound existing Codex chat; the returned answer appeared in the dashboard with no substitute model process or worker tasks.

Anthropic support has not been live-tested because no credential is configured. Reload Codex to discover newly added MCP tools. The current chat can use scripts/session-relay.py immediately without restarting. Automatic pickup is configured through a separate in-thread heartbeat; the verified synchronous round trip does not measure scheduler latency.

Warnings from the build: the React Flow/animation bundle exceeds Vite's default 500 KiB advisory threshold (about 187 KiB gzipped). The backend test client emits a Starlette/httpx deprecation notice. Neither prevented successful validation.
