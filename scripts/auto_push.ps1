param(
  [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
  [int]$DebounceSeconds = 6,
  [string]$Remote = 'origin',
  [string]$Branch = '',
  [string]$MessagePrefix = 'Auto-sync',
  [switch]$SyncOnStart,
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

function Should-IgnorePath {
  param([string]$FullPath)
  if (-not $FullPath) { return $true }
  $p = $FullPath.Replace('/', '\')
  if ($p -match '\\\.git(\\|$)') { return $true }
  if ($p -match '\\__pycache__(\\|$)') { return $true }
  if ($p -match '\\data\\tts_cache(\\|$)') { return $true }
  if ($p -match '\\(venv|env|\\.venv)(\\|$)') { return $true }
  return $false
}

function Invoke-AutoSync {
  if (-not (Test-Path (Join-Path $RepoRoot '.git'))) {
    throw "Not a git repo: $RepoRoot"
  }

  Push-Location $RepoRoot
  try {
    $mergeHead = Invoke-Git -Args @('rev-parse', '-q', '--verify', 'MERGE_HEAD') -AllowFailure
    if ($mergeHead) {
      Write-Warning "Merge in progress; skipping auto-sync."
      return
    }

    $status = Invoke-Git -Args @('status', '--porcelain')
    if (-not $status.Trim()) {
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
    Write-Host "[$ts] Pushing $fileCount file(s) -> $Remote/$b"
    Invoke-Git -Args @('push', $Remote, $b)
  }
  catch {
    Write-Host ("Auto-sync failed: " + $_.Exception.Message) -ForegroundColor Red
    Write-Host "Fix the issue, then run: scripts/auto_push_once.ps1" -ForegroundColor Yellow
  }
  finally {
    Pop-Location
  }
}

if ($DebounceSeconds -lt 1) { $DebounceSeconds = 1 }

Write-Host "Repo: $RepoRoot"
Write-Host "Remote: $Remote  Branch: " -NoNewline
try { Write-Host (Get-CurrentBranch) } catch { Write-Host "(unknown)" }
Write-Host "Debounce: $DebounceSeconds second(s)"
Write-Host "Watching for changes... (Ctrl+C to stop)"

$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $RepoRoot
$watcher.IncludeSubdirectories = $true
$watcher.NotifyFilter = [IO.NotifyFilters]'FileName, LastWrite, DirectoryName, Size'
$watcher.EnableRaisingEvents = $true

$subs = @()
$subs += Register-ObjectEvent -InputObject $watcher -EventName Changed -SourceIdentifier 'lc.fs.changed'
$subs += Register-ObjectEvent -InputObject $watcher -EventName Created -SourceIdentifier 'lc.fs.created'
$subs += Register-ObjectEvent -InputObject $watcher -EventName Deleted -SourceIdentifier 'lc.fs.deleted'
$subs += Register-ObjectEvent -InputObject $watcher -EventName Renamed -SourceIdentifier 'lc.fs.renamed'

$pending = $false
$lastEventUtc = [DateTime]::UtcNow

try {
  if ($SyncOnStart) {
    Invoke-AutoSync
  }

  while ($true) {
    $ev = Wait-Event -Timeout 1
    while ($null -ne $ev) {
      try {
        $full = $ev.SourceEventArgs.FullPath
        if (-not (Should-IgnorePath -FullPath $full)) {
          $pending = $true
          $lastEventUtc = [DateTime]::UtcNow
        }
      }
      finally {
        Remove-Event -EventIdentifier $ev.EventIdentifier -ErrorAction SilentlyContinue
      }
      $ev = Wait-Event -Timeout 0
    }

    if ($pending -and (([DateTime]::UtcNow - $lastEventUtc).TotalSeconds -ge $DebounceSeconds)) {
      $pending = $false
      Invoke-AutoSync
    }
  }
}
finally {
  foreach ($s in $subs) {
    try { Unregister-Event -SubscriptionId $s.Id -ErrorAction SilentlyContinue } catch {}
  }
  try { $watcher.Dispose() } catch {}
}
