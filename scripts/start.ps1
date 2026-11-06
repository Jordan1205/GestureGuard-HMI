$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { throw 'Run scripts/install.ps1 first.' }
    if (-not (Test-Path -LiteralPath 'frontend\dist\index.html')) { throw 'Run npm run build in frontend first.' }
    Write-Host 'GestureGuard HMI: http://127.0.0.1:8765. Press Ctrl+C to stop.'
    & '.\.venv\Scripts\python.exe' -m uvicorn gestureguard.api:app --app-dir backend --host 127.0.0.1 --port 8765
} finally { Pop-Location }
