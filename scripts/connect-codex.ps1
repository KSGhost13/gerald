$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$bridgePath = Join-Path $projectRoot 'backend\gerald\mcp_bridge.py'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Run scripts/setup.ps1 first' }
codex mcp add gerald -- $pythonPath $bridgePath
if ($LASTEXITCODE -ne 0) { throw 'Codex MCP registration failed' }
Write-Host 'GERALD MCP registered. Keep the dashboard server running and restart Codex to load the tools.'
