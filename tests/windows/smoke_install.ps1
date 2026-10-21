# OptimaX - installer smoke test for CI (GitHub Actions, Windows runner, administrator).
# Silent install -> files, Start menu shortcuts, uninstall entry -> installed OptimaX.exe --selftest --selftest-ui
# -> rescue launcher (unattended) -> silent uninstall -> everything removed.
#   pwsh tests/windows/smoke_install.ps1 -Setup Output\OptimaX-Setup-6.3.exe -Out smoke
# Keep this file ASCII-only: Windows PowerShell 5.1 misreads UTF-8 without a BOM.
param(
    [Parameter(Mandatory = $true)][string]$Setup,
    [string]$Out = "smoke",
    [string]$Version = ""
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Out = (Resolve-Path $Out).Path
$Setup = (Resolve-Path $Setup).Path
$results = New-Object System.Collections.Generic.List[object]

function Check([string]$name, [bool]$ok, [string]$detail = "") {
    $results.Add([pscustomobject]@{ check = $name; ok = $ok; detail = $detail })
    $mark = if ($ok) { "ok  " } else { "FAIL" }
    Write-Host "$mark $name $detail"
}

function Wait-Gone([string]$path, [int]$seconds) {
    for ($i = 0; $i -lt $seconds * 2; $i++) {
        if (-not (Test-Path $path)) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return -not (Test-Path $path)
}

$appId = "{8F3C2A61-4B7E-4D21-9C5A-0E6F1B2D7A44}_is1"
$uninstKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\$appId"
$app = Join-Path $env:ProgramFiles "OptimaX"
$menu = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs"
$dash = [char]0x2014
$rescueLnk = Join-Path $menu ("OptimaX $dash Emergency rollback.lnk")

# 1. silent install (English, so the shortcut name is predictable)
$p = Start-Process -FilePath $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/LANG=en", "/LOG=`"$Out\install.log`"" -Wait -PassThru
Check "installer exit code" ($p.ExitCode -eq 0) "($($p.ExitCode))"
foreach ($f in "OptimaX.exe", "OptimaX-Rescue.cmd", "unins000.exe") {
    Check "installed $f" (Test-Path (Join-Path $app $f))
}
Check "Start menu: OptimaX" (Test-Path (Join-Path $menu "OptimaX.lnk"))
Check "Start menu: emergency rollback" (Test-Path $rescueLnk) $rescueLnk
$reg = Get-ItemProperty -Path $uninstKey -ErrorAction SilentlyContinue
Check "uninstall entry" ($null -ne $reg) $uninstKey
if ($reg -and $Version) { Check "uninstall entry version" ($reg.DisplayVersion -eq $Version) "$($reg.DisplayVersion)" }
$lang = (Get-ItemProperty -Path "HKCU:\Software\X44TO\OptimaX" -ErrorAction SilentlyContinue).Language
Check "language from installer" ($lang -eq "en") "$lang"

# 2. the installed program checks itself (preview mode, temporary settings: changes nothing)
$report = Join-Path $Out "selftest-installed.json"
$p = Start-Process -FilePath (Join-Path $app "OptimaX.exe") -ArgumentList "--selftest=`"$report`"", "--selftest-ui" -Wait -PassThru
$ok = $false
$detail = "exit $($p.ExitCode)"
if (Test-Path $report) {
    $rep = Get-Content $report -Raw -Encoding UTF8 | ConvertFrom-Json
    $ok = ($p.ExitCode -eq 0) -and $rep.ok
    $failed = @($rep.checks | Where-Object { -not $_.ok } | ForEach-Object { "$($_.name): $($_.error)" })
    if ($failed.Count) { $detail += "; " + ($failed -join "; ") }
} else { $detail += "; no report" }
Check "installed OptimaX.exe --selftest-ui" $ok $detail

# 3. rescue launcher runs unattended (nothing to roll back on a clean machine) and does not hang
$p = Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "`"$app\OptimaX-Rescue.cmd`"", "/all" -Wait -PassThru -NoNewWindow
Check "rescue launcher /all" ($p.ExitCode -eq 0) "($($p.ExitCode))"

# 4. silent uninstall (the uninstaller copies itself to %TEMP% and returns early, so wait for the files)
$p = Start-Process -FilePath (Join-Path $app "unins000.exe") -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART" -Wait -PassThru
Check "uninstaller started" ($p.ExitCode -eq 0) "($($p.ExitCode))"
Check "program files removed" (Wait-Gone (Join-Path $app "OptimaX.exe") 120)
Check "uninstall entry removed" (Wait-Gone $uninstKey 30)
Check "Start menu shortcuts removed" ((Wait-Gone (Join-Path $menu "OptimaX.lnk") 30) -and (-not (Test-Path $rescueLnk)))
$tasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "OptimaX*" } | ForEach-Object { $_.TaskName })
Check "no OptimaX scheduled tasks left" ($tasks.Count -eq 0) ($tasks -join ", ")

# summary
$bad = @($results | Where-Object { -not $_.ok })
$md = @("### Installer smoke test: " + $(if ($bad.Count) { "FAILED" } else { "passed" }), "", "| check | result | details |", "|---|---|---|")
foreach ($r in $results) { $md += "| $($r.check) | $(if ($r.ok) { 'ok' } else { '**FAIL**' }) | $($r.detail -replace '\|', '/') |" }
$md -join "`n" | Set-Content -Path (Join-Path $Out "smoke.md") -Encoding UTF8
$results | ConvertTo-Json | Set-Content -Path (Join-Path $Out "smoke.json") -Encoding UTF8
if ($bad.Count) { exit 1 }
exit 0
