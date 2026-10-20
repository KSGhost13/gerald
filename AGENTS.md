# G.E.R.A.L.D.

Backend: Python 3.12+, FastAPI, asyncio, SQLite. Frontend: React, TypeScript, Vite, Tailwind, React Flow.
Run backend tests with PYTHONPATH=backend python -m pytest tests -q. Build UI with npm run build in frontend.
Worker tools operate in data/workspace. Public progress summaries and outputs belong in events; do not expose private model reasoning.
Use the gerald MCP tools to inspect or control this dashboard when the backend is running.
The cloud provider uses Codex CLI sign-in. The default is local Ollama. Do not change the user's global provider settings.

When handling dashboard directives in the bound existing Codex chat, follow SESSION-BRAIN.md. Use the session inbox/claim/respond protocol; never loop a session response back through gerald_mission. Empty inbox checks should stay quiet. Session bindings, claims and reply payloads belong in ignored data/, not Git.
