$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path 'frontend\dist\index.html')) { throw 'Run scripts/setup.ps1 first' }
$listenPort = if ($env:GERALD_PORT) { $env:GERALD_PORT } else { '8765' }
if (Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue) { throw "Port $listenPort already has a listener" }
$env:PYTHONPATH = Join-Path $projectRoot 'backend'
$process = Start-Process -FilePath '.\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','gerald.main:app','--host','127.0.0.1','--port',$listenPort -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput 'data\server.log' -RedirectStandardError 'data\server-error.log' -PassThru
$process.Id | Set-Content 'data\server.pid'
Write-Host "G.E.R.A.L.D. started as PID $($process.Id) at http://127.0.0.1:$listenPort"
