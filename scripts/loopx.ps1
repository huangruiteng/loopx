#requires -Version 7.0

$ErrorActionPreference = "Stop"
$pointerPath = $env:LOOPX_CURRENT_RELEASE_FILE
if ([string]::IsNullOrWhiteSpace($pointerPath)) {
    $pointerPath = Join-Path $HOME ".local/share/loopx/current-release.json"
}
if (-not (Test-Path -LiteralPath $pointerPath -PathType Leaf)) {
    throw "LoopX current release pointer was not found: $pointerPath"
}

$pointer = Get-Content -LiteralPath $pointerPath -Raw -Encoding UTF8 | ConvertFrom-Json
$releaseRoot = [string]$pointer.release_root
$python = [string]$pointer.python
if ([string]::IsNullOrWhiteSpace($releaseRoot) -or -not (Test-Path -LiteralPath $releaseRoot -PathType Container)) {
    throw "LoopX current release root is invalid: $releaseRoot"
}
if ([string]::IsNullOrWhiteSpace($python) -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "LoopX configured Python executable is invalid: $python"
}
$entry = Join-Path $releaseRoot "scripts/loopx_entry.py"
if (-not (Test-Path -LiteralPath $entry -PathType Leaf)) {
    throw "LoopX Windows entry script was not found: $entry"
}

$env:LOOPX_RELEASE_ROOT = $releaseRoot
$env:LOOPX_COMMAND_PATH = $PSCommandPath
& $python -I $entry @args
exit $LASTEXITCODE
