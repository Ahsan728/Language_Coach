param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [string]$Remote = 'origin',
  [string]$Branch = '',
  [string]$MessagePrefix = 'Auto-sync',
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# PowerShell 7+: avoid treating stderr from native commands as errors
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
  $PSNativeCommandUseErrorActionPreference = $false
}

function Invoke-Git {
  param(
    [Parameter(Mandatory = $true)][string[]]$Args,
    [switch]$AllowFailure
  )

  if ($DryRun) {
    $sub = ($Args[0] | ForEach-Object { $_.ToLowerInvariant() })
    $mutating = @(
      'add', 'commit', 'push', 'pull', 'merge', 'rebase', 'checkout', 'switch',
      'reset', 'rm', 'mv', 'tag', 'stash', 'cherry-pick'
    )
    if ($mutating -contains $sub) {
      Write-Host ('[dry-run] git ' + ($Args -join ' '))
      return ''
    }
  }

  $prevEap = $ErrorActionPreference
  try {
    $ErrorActionPreference = 'Continue'
    $out = & git @Args 2>&1
  }
  finally {
    $ErrorActionPreference = $prevEap
  }
  if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
    throw ("git " + ($Args -join ' ') + "`n" + ($out -join "`n"))
  }
  return ($out -join "`n")
}

function Get-CurrentBranch {
  if ($Branch) { return $Branch }
  $b = (Invoke-Git -Args @('branch', '--show-current')).Trim()
  if (-not $b) { throw "Could not determine current branch." }
  return $b
}

function Ensure-Repo {
  if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
    throw "Not a git repo: $RepoRoot"
  }
}

function Invoke-AutoSync {
  Ensure-Repo
  Push-Location $RepoRoot
  try {
    $mergeHead = Invoke-Git -Args @('rev-parse', '-q', '--verify', 'MERGE_HEAD') -AllowFailure
    if ($mergeHead) {
      Write-Warning "Merge in progress; skipping auto-sync."
      return
    }

    $status = Invoke-Git -Args @('status', '--porcelain')
    if (-not $status.Trim()) {
      Write-Host "Clean working tree (nothing to sync)."
      return
    }

    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $lines = $status -split "`n" | Where-Object { $_.Trim() }
    $fileCount = $lines.Count

    if ($DryRun) {
      $b = Get-CurrentBranch
      Write-Host "[$ts] Would commit+push $fileCount file(s) -> $Remote/$b"
      return
    }

    Invoke-Git -Args @('add', '-A')
    $nameStatus = Invoke-Git -Args @('diff', '--cached', '--name-status')
    if (-not $nameStatus.Trim()) {
      Write-Host "No staged changes after add (likely ignored-only changes)."
      return
    }

    $nsLines = $nameStatus -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    $fileCount = $nsLines.Count

    $maxFiles = 50
    $fileLines = @()
    foreach ($l in ($nsLines | Select-Object -First $maxFiles)) {
      $fileLines += ($l -replace "`t", ' ')
    }
    if ($nsLines.Count -gt $maxFiles) {
      $fileLines += "... (+$($nsLines.Count - $maxFiles) more)"
    }

    $stat = Invoke-Git -Args @('diff', '--cached', '--stat')
    $subject = "${MessagePrefix}: $ts ($fileCount file(s))"
    $bodyLines = @('Files:') + ($fileLines | ForEach-Object { " - $($_)" }) + @('', 'Stat:', $stat)
    $body = $bodyLines -join "`n"

    Invoke-Git -Args @('commit', '-m', $subject, '-m', $body) | Out-Null

    $b = Get-CurrentBranch
    Write-Host "Pushing to $Remote/$b ..."
    Invoke-Git -Args @('push', $Remote, $b)
    Write-Host "Done."
  }
  finally {
    Pop-Location
  }
}

Invoke-AutoSync
