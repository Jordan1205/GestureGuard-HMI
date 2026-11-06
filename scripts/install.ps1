$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
        py -3.11 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is required.' }
    }
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements-lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python installation failed.' }
    & '.\.venv\Scripts\python.exe' scripts/download_model.py
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed.' }
    Push-Location -LiteralPath frontend
    try {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed.' }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
} finally { Pop-Location }
