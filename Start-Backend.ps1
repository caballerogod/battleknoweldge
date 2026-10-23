$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) { throw 'Сначала выполните Setup.ps1 или создайте .venv по README.md' }
if ((Test-Path -LiteralPath 'backend/.env') -and (Select-String -LiteralPath 'backend/.env' -Pattern '^\s*AI_PROVIDER\s*=\s*ollama\s*$' -Quiet)) {
    & (Join-Path $PSScriptRoot 'Start-Local-AI.ps1')
}
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'backend')
& (Join-Path $PSScriptRoot '.venv/Scripts/python.exe') -m uvicorn app.main:app --host 127.0.0.1 --port 8000

