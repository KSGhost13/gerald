$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $projectRoot 'data\server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Host 'No managed background server PID found.'; exit 0 }
$serverPid = [int](Get-Content -LiteralPath $pidFile)
$serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid"
if (-not $serverProcess) { Write-Host 'Server is already stopped.'; exit 0 }
$expectedPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if ($serverProcess.ExecutablePath -ne $expectedPython -or $serverProcess.CommandLine -notlike '*gerald.main:app*') {
    throw 'PID identity mismatch; refusing to stop another process.'
}
# Windows terminates the process tree; the provider job object also closes child jobs.
taskkill /PID $serverPid /T /F
if ($LASTEXITCODE -ne 0) { throw 'Could not terminate the server process tree.' }
Write-Host 'G.E.R.A.L.D. stopped. Ollama remains running.'
