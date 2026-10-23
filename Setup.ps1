$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    & py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Установите Python 3.11+ с python.org. См. README.md.' }
}
$battlePython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath 'backend/.env')) {
    Copy-Item -LiteralPath 'backend/.env.example' -Destination 'backend/.env'
}
& $battlePython -m pip install -r backend/requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить Python-зависимости.' }
Set-Location -LiteralPath (Join-Path $PSScriptRoot 'frontend')
& npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Не удалось установить frontend или модель. Проверьте сеть и README.md.' }
Write-Host 'Готово. Откройте два терминала: Start-Backend.ps1 и Start-Frontend.ps1.'

