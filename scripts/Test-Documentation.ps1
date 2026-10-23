[CmdletBinding()]
param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
$taskSpec = '.kiro/specs/ring-video-aws-storage'
$taskFiles = @(
    'README.md',
    "$taskSpec/requirements.md",
    "$taskSpec/design.md",
    "$taskSpec/tasks.md",
    "$taskSpec/decisions.md",
    "$taskSpec/sources.md",
    'docs/operations.md',
    'docs/reviews/2026-09-22-documentation-review.md'
)
$taskErrors = [System.Collections.Generic.List[string]]::new()
$taskTexts = @{}
$taskLocalLinks = 0

foreach ($taskFile in $taskFiles) {
    $taskPath = Join-Path $taskRoot $taskFile
    if (-not (Test-Path -LiteralPath $taskPath -PathType Leaf)) {
        $taskErrors.Add("Missing document: $taskFile")
        continue
    }
    $taskRaw = Get-Content -Raw -LiteralPath $taskPath -Encoding UTF8
    $taskTexts[$taskFile] = $taskRaw
    $taskFence = $null
    $taskVisible = [System.Collections.Generic.List[string]]::new()
    foreach ($taskLine in ($taskRaw -split '\r?\n')) {
        if ($taskLine -match '^\s*(`{3,}|~{3,})') {
            $taskMarker = $Matches[1]
            if ($null -eq $taskFence) {
                $taskFence = $taskMarker
            } elseif ($taskMarker[0] -eq $taskFence[0] -and $taskMarker.Length -ge $taskFence.Length) {
                $taskFence = $null
            }
            continue
        }
        if ($null -eq $taskFence) { $taskVisible.Add($taskLine) }
    }
    if ($null -ne $taskFence) { $taskErrors.Add("Unclosed code fence: $taskFile") }
    foreach ($taskLink in [regex]::Matches(($taskVisible -join "`n"), '\[[^\]]+\]\((?<target>[^)]+)\)')) {
        $taskTarget = $taskLink.Groups['target'].Value.Trim().Trim('<', '>')
        if ($taskTarget -match '^(https?://|mailto:|#)') { continue }
        $taskTarget = ($taskTarget -split '#', 2)[0]
        $taskTarget = [Uri]::UnescapeDataString($taskTarget)
        $taskLocalLinks++
        $taskResolved = Join-Path (Split-Path -Parent $taskPath) $taskTarget
        if (-not (Test-Path -LiteralPath $taskResolved)) {
            $taskErrors.Add("Broken local file link in ${taskFile}: $taskTarget")
        }
    }
}

if ($taskTexts.Count -ne $taskFiles.Count) {
    throw ($taskErrors -join "`n")
}
$taskReqText = $taskTexts["$taskSpec/requirements.md"]
$taskDesignText = $taskTexts["$taskSpec/design.md"]
$taskPlanText = $taskTexts["$taskSpec/tasks.md"]
$taskReqIds = @([regex]::Matches($taskReqText, '(?m)^- \*\*(R\d+\.\d+)\*\*') | ForEach-Object { $_.Groups[1].Value })
$taskPropertyIds = @([regex]::Matches($taskDesignText, '(?m)^\| (P\d+) \|') | ForEach-Object { $_.Groups[1].Value })
$taskNumbers = @([regex]::Matches($taskPlanText, '(?m)^- \[ \] (\d+)\.') | ForEach-Object { [int]$_.Groups[1].Value })
$taskMappedReqs = @([regex]::Matches($taskPlanText, '(?m)^  - Requirements: (.+)$') | ForEach-Object {
    [regex]::Matches($_.Groups[1].Value, '\bR\d+\.\d+\b') | ForEach-Object { $_.Value }
})
$taskMappedProperties = @([regex]::Matches($taskPlanText, '(?m)^  - Properties: (.+)$') | ForEach-Object {
    [regex]::Matches($_.Groups[1].Value, '\bP\d+\b') | ForEach-Object { $_.Value }
})

foreach ($taskId in $taskReqIds) {
    if ($taskId -notin $taskMappedReqs) { $taskErrors.Add("Unmapped requirement: $taskId") }
}
foreach ($taskId in $taskPropertyIds) {
    if ($taskId -notin $taskMappedProperties) { $taskErrors.Add("Unmapped correctness property: $taskId") }
}
foreach ($taskFile in $taskFiles) {
    foreach ($taskRef in [regex]::Matches($taskTexts[$taskFile], '\bR\d+\.\d+\b')) {
        if ($taskRef.Value -notin $taskReqIds) { $taskErrors.Add("Unknown requirement in ${taskFile}: $($taskRef.Value)") }
    }
    foreach ($taskRef in [regex]::Matches($taskTexts[$taskFile], '\bP\d+\b')) {
        if ($taskRef.Value -notin $taskPropertyIds) { $taskErrors.Add("Unknown property in ${taskFile}: $($taskRef.Value)") }
    }
}
if (($taskReqIds | Select-Object -Unique).Count -ne $taskReqIds.Count) { $taskErrors.Add('Duplicate requirement IDs') }
if (($taskPropertyIds | Select-Object -Unique).Count -ne $taskPropertyIds.Count) { $taskErrors.Add('Duplicate property IDs') }
if (($taskNumbers -join ',') -ne ((1..15) -join ',')) { $taskErrors.Add('Expected 15 ordered, unchecked implementation tasks') }
if ($taskPlanText -match '(?im)^- \[x\]') { $taskErrors.Add('Implementation task marked complete during documentation-only review') }
if ($taskReqIds.Count -ne 52 -or $taskPropertyIds.Count -ne 20) { $taskErrors.Add('Review counts differ from README: expected 52 criteria and 20 properties') }

$taskBefore = Join-Path $taskRoot 'docs/reviews/2026-09-22-before'
$taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskBefore 'manifest.json') | ConvertFrom-Json
foreach ($taskEntry in $taskManifest) {
    $taskCopy = Join-Path $taskBefore $taskEntry.Snapshot
    if ((Get-FileHash -LiteralPath $taskCopy -Algorithm SHA256).Hash -ne $taskEntry.SHA256) {
        $taskErrors.Add("Before-edit snapshot hash changed: $($taskEntry.Snapshot)")
    }
}
$taskPreserved = Get-Content -Raw -LiteralPath (Join-Path $taskBefore 'preserved-files.json') | ConvertFrom-Json
foreach ($taskEntry in $taskPreserved) {
    if ((Get-FileHash -LiteralPath (Join-Path $taskRoot $taskEntry.Path) -Algorithm SHA256).Hash -ne $taskEntry.SHA256) {
        $taskErrors.Add("Preserved original/configuration hash changed: $($taskEntry.Path)")
    }
}

if ($taskErrors.Count -gt 0) { throw ($taskErrors -join "`n") }
"Documentation validation PASS ($([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')))"
"Project folder: $taskRoot"
"Active Markdown documents: $($taskFiles.Count)"
"Unique acceptance criteria: $($taskReqIds.Count); all mapped to implementation tasks"
"Correctness properties: $($taskPropertyIds.Count); all mapped to implementation tasks"
"Ordered implementation tasks: $($taskNumbers.Count); all unchecked"
"Local Markdown file links checked: $taskLocalLinks"
'Unknown requirement/property references: 0; unclosed code fences: 0'
"Before-edit snapshots verified: $(@($taskManifest).Count)"
"Untouched original/configuration files verified: $(@($taskPreserved).Count)"
'Scope: documentation structure and preservation only; no remote-link, Markdown-anchor, application, AWS or live Ring validation.'
