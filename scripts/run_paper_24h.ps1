<#
.SYNOPSIS
  24-часовой paper-прогон (PowerShell версия).

.DESCRIPTION
  Запускает prod_core.runner в paper-режиме с ограничением 86400 секунд,
  отслеживает падения процесса и перезапускает до MAX_RESTARTS раз,
  ведёт лог и экспортирует результаты. После завершения удаляет старые
  каталоги reports/run_*, оставляя два последних.

.NOTES
  Требуется активированное виртуальное окружение .venv и MODE=paper.
#>

[CmdletBinding()]
param (
    [int]$MaxSeconds = 86400,
    [int]$MaxRestarts = $(if ($env:MAX_RESTARTS) { [int]$env:MAX_RESTARTS } else { 5 }),
    [int]$RestartDelaySec = $(if ($env:RESTART_DELAY_SEC) { [int]$env:RESTART_DELAY_SEC } else { 30 }),
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunnerArgs
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    throw "Не найден .venv\Scripts\python.exe — создайте виртуальное окружение (python -m venv .venv)."
}

$runId = Get-Date -Format 'yyyyMMdd_HHmm'
$env:RUN_ID = $runId
$outDir = "reports/run_$runId"
$logDir = 'logs'
$dbPath = if ($env:PERSIST_DB_PATH) { $env:PERSIST_DB_PATH } else { 'storage/crupto.db' }

foreach ($dir in @($outDir, $logDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

$logFile = Join-Path $logDir "paper24_${runId}.log"
if (Test-Path $logFile) {
    Remove-Item -LiteralPath $logFile
}
Write-Host "[crupto] starting 24-hour paper run (output: $outDir)"

function Remove-StaleRunDirectories {
    $runDirs = Get-ChildItem -Path 'reports' -Directory -Filter 'run_*' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending
    if ($null -eq $runDirs) {
        return
    }
    if ($runDirs.Count -le 2) {
        return
    }
    foreach ($dir in $runDirs[2..($runDirs.Count - 1)]) {
        Write-Host "[crupto] removing stale run directory: $($dir.FullName)"
        Remove-Item -LiteralPath $dir.FullName -Recurse -Force
    }
}

$attempt = 1
$runStatus = 1

while ($true) {
    Write-Host "[crupto] runner attempt $attempt (max $MaxRestarts)"
    $arguments = @('-m', 'prod_core.runner', '--max-seconds', $MaxSeconds.ToString())
    if ($RunnerArgs) {
        $arguments += $RunnerArgs
    }

    $prevPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & .\.venv\Scripts\python.exe @arguments 2>&1 | Tee-Object -FilePath $logFile -Append
        $runStatus = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $prevPreference
    }

    if ($runStatus -eq 0 -or $runStatus -eq 124) {
        Write-Host "[crupto] runner completed with status $runStatus"
        break
    }

    if ($attempt -ge $MaxRestarts) {
        Write-Warning "[crupto] runner failed with status $runStatus — достигнут лимит перезапусков ($MaxRestarts)."
        break
    }

    Write-Warning "[crupto] runner crashed with status $runStatus, retry in $RestartDelaySec sec..."
    Start-Sleep -Seconds $RestartDelaySec
    $attempt += 1
}

& .\.venv\Scripts\python.exe -m prod_core.persist.export_run --db $dbPath --out $outDir --log $logFile --run $runId
Remove-StaleRunDirectories

Write-Host "[crupto] 24-hour run finished with status $runStatus"
exit $runStatus

