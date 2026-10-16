[CmdletBinding(SupportsShouldProcess)]
param()

$ErrorActionPreference = 'Stop'
$cleanupRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$rootItem = Get-Item -LiteralPath $cleanupRoot -Force
if ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Project root must be an ordinary directory.' }
foreach ($required in @('src\main.cpp','games','clean\games','shared-assets','build\scene','pristine.zip','build-sets.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $cleanupRoot $required))) { throw "Required project content missing: $required" }
}

$buildRoot = [IO.Path]::GetFullPath((Join-Path $cleanupRoot 'build'))
$keptScene = [IO.Path]::GetFullPath((Join-Path $buildRoot 'scene'))
$allowedTop = @('cases','baselines','evidence') | ForEach-Object { [IO.Path]::GetFullPath((Join-Path $cleanupRoot $_)) }
$targets = @($allowedTop | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-Item -LiteralPath $_ -Force })
$targets += Get-ChildItem -LiteralPath $buildRoot -Force | Where-Object { $_.FullName -ne $keptScene }
$plan = @()

# Validate every concrete target before removing anything. Never follow a link.
foreach ($item in $targets) {
    $absolute = [IO.Path]::GetFullPath($item.FullName)
    if (-not $absolute.StartsWith($cleanupRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw "Target escapes project: $absolute" }
    if ($absolute -notin $allowedTop -and [IO.Path]::GetDirectoryName($absolute) -ne $buildRoot) { throw "Unapproved target: $absolute" }
    if ($absolute -eq $keptScene -or $keptScene.StartsWith($absolute + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'The current asset snapshot must be preserved.' }
    $contents = @($item)
    if ($item.PSIsContainer) { $contents += Get-ChildItem -LiteralPath $absolute -Recurse -Force }
    if ($contents | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw "Linked content found: $absolute" }
    $bytes = [long](($contents | Where-Object { -not $_.PSIsContainer } | Measure-Object -Property Length -Sum).Sum)
    $plan += [pscustomobject]@{Path=$absolute;Bytes=$bytes}
}

$removed = @()
try {
    foreach ($item in $plan) {
        if ($PSCmdlet.ShouldProcess($item.Path,'Delete obsolete build/test history')) {
            Remove-Item -LiteralPath $item.Path -Recurse -Force
            $removed += $item
        }
    }
} finally {
    if (-not $WhatIfPreference) {
        $bytes = [long](($removed | Measure-Object -Property Bytes -Sum).Sum)
        $report = [pscustomobject]@{Completed=($removed.Count -eq $plan.Count);CompletedAt=[DateTimeOffset]::Now.ToString('o');RemovedBytes=$bytes;RemovedGiB=[Math]::Round($bytes/1GB,3);Removed=$removed;GamesLaunched=$false}
        $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $cleanupRoot 'state\cleanup.json') -Encoding utf8
        Write-Output "Removed $([Math]::Round($bytes/1GB,2)) GiB of obsolete history."
    }
}
