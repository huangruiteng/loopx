#requires -Version 7.0

[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$InstallRoot = (Join-Path $HOME ".local/share/loopx"),
    [string]$BinDir = (Join-Path $HOME ".local/bin"),
    [string]$SkillsDir = "",
    [switch]$SkipSkills,
    [switch]$AddToUserPath
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($SkillsDir)) {
    $codexHome = if ([string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        Join-Path $HOME ".codex"
    } else {
        $env:CODEX_HOME
    }
    $SkillsDir = Join-Path $codexHome "skills"
}

$previousPythonPath = $env:PYTHONPATH
$env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
    $repoRoot
} else {
    "$repoRoot$([IO.Path]::PathSeparator)$previousPythonPath"
}
try {
    $installerArgs = @(
        "-m", "loopx.windows_install",
        "--source-root", $repoRoot,
        "--install-root", $InstallRoot,
        "--bin-dir", $BinDir,
        "--skills-dir", $SkillsDir,
        "--python", $Python
    )
    if ($SkipSkills) {
        $installerArgs += "--skip-skills"
    }
    & $Python @installerArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

if ($AddToUserPath) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $entries = @($userPath -split ";" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    $alreadyPresent = $entries | Where-Object {
        [string]::Equals($_.TrimEnd("\\"), $BinDir.TrimEnd("\\"), [StringComparison]::OrdinalIgnoreCase)
    }
    if (-not $alreadyPresent) {
        $updatedPath = (@($entries) + $BinDir) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $updatedPath, "User")
    }
    if (-not (($env:Path -split ";") -contains $BinDir)) {
        $env:Path = "$BinDir;$env:Path"
    }
    Write-Output "LoopX Windows user PATH includes: $BinDir"
}
