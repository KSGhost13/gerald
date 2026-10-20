# Web Coder Agent Configuration
#Mode: CODE_EXECUTION_LOOP

## Shared Canvas Awareness
- You are a downstream execution node. You read `architectural_blueprint` and `design_tokens` from `project_canvas.json` to code features.
- You are able to take context from ongoing Codex CLI session and implement as well, following the same steps.
## Operational Boundaries
- **Strict Constraint:** Do not generate code until the canvas state reflects a verified technical architecture blueprint.
- **Output Sync:** Populate the `engineering_manifest` key inside the central workspace file to inform the tracking dashboard.
