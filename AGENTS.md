# G.E.R.A.L.D.

Backend: Python 3.12+, FastAPI, asyncio, SQLite. Frontend: React, TypeScript, Vite, Tailwind, React Flow.
Run backend tests with PYTHONPATH=backend python -m pytest tests -q. Build UI with npm run build in frontend.
Worker tools operate in data/workspace. Public progress summaries and outputs belong in events; do not expose private model reasoning.
Human-readable business guides may live at the absolute GERALD_BUSINESS_DOCS directory configured in ignored .env; use that canonical location for document edits, not stale copies in data/workspace/business-launch. Runtime JSON/SQLite, claims, secrets and ledgers remain in data/. The opt-in business_docs_read tool injects only bounded, allowlisted reference excerpts for agents; it grants no write or arbitrary Desktop access. Preserve the document reader's path/link protections.
Use the gerald MCP tools to inspect or control this dashboard when the backend is running.
The cloud provider uses Codex CLI sign-in. The default is local Ollama. Do not change the user's global provider settings.

When handling dashboard directives in the bound existing Codex chat, follow SESSION-BRAIN.md. Use the session inbox/claim/respond protocol; never loop a session response back through gerald_mission. Empty inbox checks should stay quiet. Session bindings, claims and reply payloads belong in ignored data/, not Git.
