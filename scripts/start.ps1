$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path 'frontend\dist\index.html')) { throw 'Run scripts/setup.ps1 first' }
$listenPort = if ($env:GERALD_PORT) { $env:GERALD_PORT } else { '8765' }
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
Write-Host "G.E.R.A.L.D. is starting at http://127.0.0.1:$listenPort. Ctrl+C stops its workers."
& .\.venv\Scripts\python.exe -m uvicorn gerald.main:app --host 127.0.0.1 --port $listenPort --timeout-graceful-shutdown 10
