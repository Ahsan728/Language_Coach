Set-StrictMode -Version Latest

function Normalize-RepoPath {
  param([string]$Path)
  if (-not $Path) { return '' }
  return ($Path -replace '\\', '/')
}

function Get-ChangeKind {
  param([string]$Status)
  if (-not $Status) { return 'update' }
  $s = $Status.Trim()
  if (-not $s) { return 'update' }
  $c = $s.Substring(0, 1).ToUpperInvariant()
  if ($c -eq 'A' -or $c -eq 'C') { return 'add' }
  if ($c -eq 'D') { return 'remove' }
  return 'update'
}

function Get-TopicsForPath {
  param([Parameter(Mandatory = $true)][string]$Path)
  $p = (Normalize-RepoPath -Path $Path).ToLowerInvariant()

  $out = New-Object System.Collections.Generic.List[string]
  if ($p -eq 'app.py' -or $p.EndsWith('/app.py')) { $out.Add('backend') }
  if ($p.StartsWith('templates/')) { $out.Add('ui') }
  if ($p -eq 'templates/base.html') { $out.Add('layout') }
  if ($p.StartsWith('static/js/')) { $out.Add('frontend') }
  if ($p.StartsWith('static/css/')) { $out.Add('styles') }
  if ($p.StartsWith('data/')) { $out.Add('content') }
  if ($p.StartsWith('scripts/')) { $out.Add('scripts') }

  if ($p -match 'activity_') { $out.Add('activities') }
  if ($p -match 'login') { $out.Add('login') }
  if ($p -match 'auth') { $out.Add('auth') }
  if ($p -match 'dashboard') { $out.Add('dashboard') }
  if ($p -match 'lesson') { $out.Add('lessons') }
  if ($p -match 'practice') { $out.Add('practice') }
  if ($p -match 'quiz') { $out.Add('quiz') }
  if ($p -match 'flashcard') { $out.Add('flashcards') }
  if ($p -match 'vocab') { $out.Add('vocabulary') }
  if ($p -match 'resource') { $out.Add('resources') }
  if ($p -match 'progress') { $out.Add('progress') }
  if ($p -match 'dictation') { $out.Add('dictation') }
  if ($p -match 'tts') { $out.Add('tts') }
  if ($p -match 'theme') { $out.Add('theme') }

  return $out
}

function Select-TopicLabels {
  param(
    [Parameter(Mandatory = $true)][System.Collections.Generic.HashSet[string]]$Topics,
    [int]$Max = 3
  )
  if (-not $Topics -or $Topics.Count -eq 0) { return @() }

  $priority = @(
    'login', 'auth',
    'dashboard', 'activities',
    'lessons', 'practice', 'quiz', 'flashcards',
    'vocabulary', 'resources', 'progress', 'dictation',
    'tts', 'theme',
    'layout',
    'styles', 'frontend', 'backend',
    'content', 'scripts',
    'ui'
  )

  $labels = @{
    login      = 'login'
    auth       = 'auth'
    dashboard  = 'dashboard'
    activities = 'activities'
    lessons    = 'lessons'
    practice   = 'practice'
    quiz       = 'quiz'
    flashcards = 'flashcards'
    vocabulary = 'vocabulary'
    resources  = 'resources'
    progress   = 'progress'
    dictation  = 'dictation'
    tts        = 'pronunciation'
    theme      = 'theme'
    layout     = 'layout'
    styles     = 'styles'
    frontend   = 'frontend'
    backend    = 'backend'
    content    = 'content'
    scripts    = 'scripts'
    ui         = 'UI'
  }

  $out = @()
  foreach ($key in $priority) {
    if (-not $Topics.Contains($key)) { continue }
    if ($labels.ContainsKey($key) -and $labels[$key]) {
      $out += $labels[$key]
    }
    else {
      $out += $key
    }
    if ($out.Count -ge $Max) { break }
  }

  return $out
}

function Format-LabelList {
  param([string[]]$Items)
  if (-not $Items -or $Items.Count -eq 0) { return '' }
  if ($Items.Count -eq 1) { return $Items[0] }
  if ($Items.Count -eq 2) { return "$($Items[0]) and $($Items[1])" }
  $head = ($Items[0..($Items.Count - 2)] -join ', ')
  return "$head, and $($Items[-1])"
}

function Get-FileBasename {
  param([string]$Path)
  $p = Normalize-RepoPath -Path $Path
  if (-not $p) { return '' }
  $parts = $p -split '/'
  return $parts[-1]
}

function Truncate-Subject {
  param(
    [string]$Text,
    [int]$MaxLen = 72
  )
  if (-not $Text) { return '' }
  if ($Text.Length -le $MaxLen) { return $Text }
  if ($MaxLen -lt 4) { return $Text.Substring(0, $MaxLen) }
  return ($Text.Substring(0, $MaxLen - 3) + '...')
}

function Get-AutoSyncSubject {
  param(
    [string]$MessagePrefix,
    [Parameter(Mandatory = $true)][string]$Timestamp,
    [Parameter(Mandatory = $true)][string[]]$NameStatusLines,
    [ValidateSet('timestamp', 'files', 'smart')][string]$Mode = 'smart',
    [int]$MaxLen = 72
  )

  $ns = @($NameStatusLines | Where-Object { $_ -and $_.Trim() })
  $fileCount = $ns.Count

  if ($Mode -eq 'timestamp') {
    $base = "$Timestamp ($fileCount file(s))"
    $subject = if ($MessagePrefix) { "$MessagePrefix: $base" } else { $base }
    return (Truncate-Subject -Text $subject -MaxLen $MaxLen)
  }

  $changes = @()
  foreach ($line in $ns) {
    $l = $line.Trim()
    if (-not $l) { continue }

    $fields = $l -split "`t"
    if ($fields.Count -ge 2) {
      $status = if ($fields[0]) { $fields[0].Trim() } else { '' }
      $path = if ($fields[$fields.Count - 1]) { $fields[$fields.Count - 1].Trim() } else { '' }
    }
    else {
      $parts = $l -split '\s+', 2
      if ($parts.Count -lt 2) { continue }
      $status = if ($parts[0]) { $parts[0].Trim() } else { '' }
      $path = if ($parts[1]) { $parts[1].Trim() } else { '' }
    }

    if (-not $status -or -not $path) { continue }
    $changes += [pscustomobject]@{ Status = $status; Path = $path }
  }

  if ($Mode -eq 'files') {
    $bases = @($changes | ForEach-Object { Get-FileBasename -Path $_.Path } | Where-Object { $_ })
    $bases = $bases | Select-Object -Unique
    $take = @($bases | Select-Object -First 3)
    $label = Format-LabelList -Items $take
    if (-not $label) { $label = 'files' }
    if ($bases.Count -gt 3) { $label = "$label..." }
    $base = "Update $label ($fileCount file(s))"
    $subject = if ($MessagePrefix) { "$MessagePrefix: $base" } else { $base }
    return (Truncate-Subject -Text $subject -MaxLen $MaxLen)
  }

  $addPaths = @()
  $removePaths = @()
  $updatePaths = @()
  foreach ($c in $changes) {
    $kind = Get-ChangeKind -Status $c.Status
    if ($kind -eq 'add') { $addPaths += $c.Path; continue }
    if ($kind -eq 'remove') { $removePaths += $c.Path; continue }
    $updatePaths += $c.Path
  }

  function Get-GroupLabel {
    param([string[]]$Paths)
    $set = New-Object System.Collections.Generic.HashSet[string]
    foreach ($p in ($Paths | Where-Object { $_ })) {
      foreach ($t in (Get-TopicsForPath -Path $p)) {
        [void]$set.Add($t)
      }
    }
    $labels = Select-TopicLabels -Topics $set -Max 3
    $label = Format-LabelList -Items $labels
    if ($label) { return $label }

    $bases = @($Paths | ForEach-Object { Get-FileBasename -Path $_ } | Where-Object { $_ } | Select-Object -First 2)
    $fallback = Format-LabelList -Items $bases
    if ($fallback) { return $fallback }
    return 'files'
  }

  $phrases = @()
  if ($addPaths.Count -gt 0) { $phrases += ("Add " + (Get-GroupLabel -Paths $addPaths)) }
  if ($removePaths.Count -gt 0) { $phrases += ("Remove " + (Get-GroupLabel -Paths $removePaths)) }
  if ($updatePaths.Count -gt 0) { $phrases += ("Update " + (Get-GroupLabel -Paths $updatePaths)) }

  $summary = ($phrases -join '; ')
  if (-not $summary) { $summary = "Update files" }

  $base = "$summary ($fileCount file(s))"
  $subject = if ($MessagePrefix) { "$MessagePrefix: $base" } else { $base }
  return (Truncate-Subject -Text $subject -MaxLen $MaxLen)
}
