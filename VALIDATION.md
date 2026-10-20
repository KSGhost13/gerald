# Verified on this machine

- Python backend: 15 automated tests pass, covering routing, lifecycle controls, cloud fallback, API/WebSocket behavior, local-only policy, parent/child process termination, persisted recovery, and the six existing-chat integration cases described below.
- TypeScript check and Vite production build pass.
- Final npm audit reports zero known vulnerabilities.
- Actual generation works through Ollama HTTP, Ollama CLI, Codex CLI cloud (existing ChatGPT sign-in), and Codex CLI local with Qwen 2.5 Coder 14B. Results: `VERIFICATION.json`.
- Official MCP client initialized the stdio bridge, discovered eleven tools (including four session tools) and retrieved live dashboard state. `codex mcp get gerald` confirms the installed registration.
- Dashboard inspected in the Codex browser; ATLAS was created using its forge form.
- Full GERALD → ATLAS → SCRIBE mission completed with zero errors. Results: `WORKFLOW-VERIFICATION.json`.

The session extension adds six tests for UI directive pickup without model generation, explicit worker routing and duplicate callback handling, wrong-chat/stale-claim rejection, pause/disconnect, persisted recovery, and an API round trip. A real directive was submitted through the dashboard and answered in the bound existing Codex chat; the returned answer appeared in the dashboard with no substitute model process or worker tasks.

Anthropic support has not been live-tested because no credential is configured. Reload Codex to discover newly added MCP tools. The current chat can use scripts/session-relay.py immediately without restarting. Automatic pickup is configured through a separate in-thread heartbeat; the verified synchronous round trip does not measure scheduler latency.

Warnings from the build: the React Flow/animation bundle exceeds Vite's default 500 KiB advisory threshold (about 184 KiB gzipped). The backend test client emits a Starlette/httpx deprecation notice. Neither prevented successful validation.
