# Verified on this machine

- Python backend: 9 automated tests pass, including live edge changes, graph cycle rejection, pause/resume, abort of current/queued work, cloud-to-local fallback, API/WebSocket behavior, remote-server rejection in local mode, actual parent/child process termination, and mission/output persistence across restarts.
- TypeScript check and Vite production build pass.
- Final npm audit reports zero known vulnerabilities.
- Actual generation works through Ollama HTTP, Ollama CLI, Codex CLI cloud (existing ChatGPT sign-in), and Codex CLI local with Qwen 2.5 Coder 14B. Results: `VERIFICATION.json`.
- Official MCP client initialized the stdio bridge, discovered seven tools and retrieved live dashboard state. `codex mcp get gerald` confirms the installed registration.
- Dashboard inspected in the Codex browser; ATLAS was created using its forge form.
- Full GERALD → ATLAS → SCRIBE mission completed with zero errors. Results: `WORKFLOW-VERIFICATION.json`.

Anthropic support has not been live-tested because no credential is configured. Codex desktop needs a restart to load its newly registered MCP tools. The bridge itself has been protocol-tested; this running chat's tool inventory is not hot-reloaded.

Warnings from the build: the React Flow/animation bundle exceeds Vite's default 500 KiB advisory threshold (about 182 KiB gzipped). The backend test client emits a Starlette/httpx deprecation notice. Neither prevented successful validation.
