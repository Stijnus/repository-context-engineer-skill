[CmdletBinding()]
param(
    [ValidateSet('claude', 'codex')]
    [string]$Mode = 'claude',
    [string]$Target,
    [string]$Source,
    [string]$Branch = 'main',
    [switch]$Pull,
    [switch]$NoBackup,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

function Show-Usage {
    @"
Update Repository Context Engineer files in a Claude Code skill install or Codex target repo.

Usage:
  powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 [options]

Options:
  -Mode <claude|codex>   Update mode. Default: claude
  -Target <path>         Destination path.
                         Default for claude: ~\.claude\skills\repository-context-engineer
                         Required for codex.
  -Source <path>         Source checkout to sync from.
                         Default: the repository containing this script.
  -Pull                  Pull the latest changes from origin/<branch> in the source checkout
                         before syncing files.
  -Branch <name>         Git branch to pull when -Pull is used. Default: main
  -NoBackup              Do not back up managed files before overwriting them.
  -Help                  Show this help text.

Examples:
  powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull
  powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull -Target "$HOME\.claude\skills\repository-context-engineer"
  powershell -ExecutionPolicy Bypass -File scripts/update_skill.ps1 -Pull -Mode codex -Target "C:\path\to\target-repo"
"@
}

function Invoke-GitCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed."
    }
}

if ($Help) {
    Show-Usage
    exit 0
}

if (-not $Source) {
    $Source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
} else {
    $Source = (Resolve-Path $Source).Path
}

if (-not $Target) {
    if ($Mode -eq 'claude') {
        $Target = Join-Path $HOME '.claude\skills\repository-context-engineer'
    } else {
        throw 'When -Mode codex is used, -Target is required.'
    }
}

switch ($Mode) {
    'claude' {
        $ManagedFiles = @(
            'SKILL.md',
            'AGENTS.md',
            'README.md',
            'USAGE.md',
            'scripts/build_context_pack.py',
            'scripts/build_context_pack_v3.py',
            'scripts/update_skill.sh',
            'scripts/update_skill.ps1',
            'examples/settings.snippets.jsonc'
        )
    }
    'codex' {
        $ManagedFiles = @(
            'AGENTS.md',
            'scripts/build_context_pack.py',
            'scripts/build_context_pack_v3.py',
            'scripts/update_skill.sh',
            'scripts/update_skill.ps1'
        )
    }
}

foreach ($rel in $ManagedFiles) {
    $sourcePath = Join-Path $Source $rel
    if (-not (Test-Path $sourcePath)) {
        throw "Managed file is missing from source checkout: $rel"
    }
}

if ($Pull) {
    if (-not (Test-Path (Join-Path $Source '.git'))) {
        throw '-Pull requires -Source to be a git checkout.'
    }

    Invoke-GitCommand -Arguments @('-C', $Source, 'fetch', 'origin', $Branch)
    $currentBranch = (& git -C $Source rev-parse --abbrev-ref HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to determine the current git branch.'
    }

    if ($currentBranch -ne $Branch) {
        Invoke-GitCommand -Arguments @('-C', $Source, 'checkout', $Branch)
    }

    Invoke-GitCommand -Arguments @('-C', $Source, 'pull', '--ff-only', 'origin', $Branch)
}

$SourceCanonical = (Resolve-Path $Source).Path
$TargetCanonical = if (Test-Path $Target) { (Resolve-Path $Target).Path } else { $null }
$SameRoot = $false
if ($SourceCanonical -and $TargetCanonical -and ($SourceCanonical -eq $TargetCanonical)) {
    $SameRoot = $true
}

if ($SameRoot) {
    Write-Host 'Source and target are the same directory. The checkout is now up to date.'
    Write-Host 'Restart Claude Code or your Codex session if it is already running.'
    exit 0
}

if (-not (Test-Path $Target)) {
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
}

$BackupRoot = $null
if (-not $NoBackup) {
    $hasExistingManagedFiles = $false
    foreach ($rel in $ManagedFiles) {
        if (Test-Path (Join-Path $Target $rel)) {
            $hasExistingManagedFiles = $true
            break
        }
    }

    if ($hasExistingManagedFiles) {
        $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $BackupRoot = Join-Path $Target ".repository-context-engineer-backups\$timestamp"

        foreach ($rel in $ManagedFiles) {
            $existingPath = Join-Path $Target $rel
            if (Test-Path $existingPath) {
                $backupPath = Join-Path $BackupRoot $rel
                $backupDir = Split-Path -Parent $backupPath
                if ($backupDir -and -not (Test-Path $backupDir)) {
                    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
                }
                Copy-Item -Path $existingPath -Destination $backupPath -Recurse -Force
            }
        }
    }
}

foreach ($rel in $ManagedFiles) {
    $sourcePath = Join-Path $Source $rel
    $targetPath = Join-Path $Target $rel
    $targetDir = Split-Path -Parent $targetPath

    if ($targetDir -and -not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    Copy-Item -Path $sourcePath -Destination $targetPath -Force
}

Write-Host "Updated Repository Context Engineer files in: $Target"
if ($BackupRoot) {
    Write-Host "Backup written to: $BackupRoot"
}
Write-Host "Mode: $Mode"
Write-Host "Source checkout: $Source"
Write-Host 'Restart Claude Code or your Codex session if it is already running.'
