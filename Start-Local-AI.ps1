$ErrorActionPreference = 'Stop'
$command = Get-Command ollama -ErrorAction SilentlyContinue
$exe = if ($command) { $command.Source } else { Join-Path $env:LOCALAPPDATA 'Programs/AIKnowledgeBattle-Ollama/ollama.exe' }
if (-not (Test-Path -LiteralPath $exe)) {
    $exe = Join-Path $env:LOCALAPPDATA 'Programs/Ollama/ollama.exe'
}
if (-not (Test-Path -LiteralPath $exe)) { throw 'Установите Ollama: https://ollama.com/download/windows, затем повторите запуск.' }
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 }
catch {
    Start-Process -FilePath $exe -ArgumentList 'serve' -WindowStyle Hidden
    $ready = $false
    for ($attempt=0; $attempt -lt 20; $attempt++) {
        Start-Sleep -Milliseconds 500
        try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $ready = $true; break } catch {}
    }
    if (-not $ready) { throw 'Не удалось запустить Ollama на 127.0.0.1:11434.' }
}
$model = 'qwen3:4b-instruct'
$envFile = Join-Path $PSScriptRoot 'backend/.env'
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in (Get-Content -LiteralPath $envFile -Encoding UTF8)) {
        if ($line -match '^\s*OLLAMA_MODEL\s*=\s*(.+)$') { $model = $Matches[1].Trim().Trim('"').Trim("'") }
    }
}
$tags = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2
if ($model -notin @($tags.models.name)) {
    & $exe pull $model
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось загрузить модель. Проверьте подключение и повторите запуск.' }
}
Write-Host "Локальная модель готова: $model. Оплата API не требуется. Теперь запустите Start-Backend.ps1 и Start-Frontend.ps1."
