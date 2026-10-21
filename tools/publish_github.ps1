<#
.SYNOPSIS
  OptimaX — публікація на GitHub: код, опис і теми репозиторію, мітки, сайт, (за бажанням) реліз з ваших exe.

.DESCRIPTION
  Запускайте з будь-якої папки:  powershell -ExecutionPolicy Bypass -File tools\publish_github.ps1 [-Release]

  Без параметрів:  завантажує код у репозиторій, ставить опис, сайт і теми, створює мітки для issues,
                   вмикає GitHub Pages і приватні звіти про вразливості.
  -Release:        ще й створює реліз v<версія> з файлів Output\ (спершу build_installer.bat і build.bat)
                   разом із SHA256SUMS.txt, OptimaX-Rescue.cmd і маніфестами winget.
  -Tag:            замість власної збірки ставить тег v<версія>: exe збирає GitHub Actions, проганяє всі
                   перевірки (зокрема твіки на справжній Windows) і сам публікує реліз.
  -NoPush:         нічого не завантажувати, лише налаштування й реліз.
  -Yes:            не питати підтвердження.

  Потрібні Git і GitHub CLI:  winget install --id Git.Git -e   і   winget install --id GitHub.cli -e

.EXAMPLE
  .\tools\publish_github.ps1
.EXAMPLE
  .\tools\publish_github.ps1 -Release
.EXAMPLE
  .\tools\publish_github.ps1 -Tag
#>
param(
    [string]$Repo = "hatogg/OptimaX-by-X44TO",
    [switch]$Release,
    [switch]$Tag,
    [switch]$NoPush,
    [switch]$Yes,
    [string]$Message = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Utf8 = New-Object System.Text.UTF8Encoding $false
if ($Release -and $Tag) { Write-Host "Виберіть одне: -Release (ваші exe) або -Tag (exe збирає GitHub Actions)." -ForegroundColor Red; exit 1 }
$Site = "https://" + $Repo.Split("/")[0].ToLower() + ".github.io/" + $Repo.Split("/")[1] + "/"

function Say([string]$Text, [string]$Color = "Gray") { Write-Host $Text -ForegroundColor $Color }
function Step([string]$Text) { Write-Host ""; Write-Host "== $Text" -ForegroundColor Cyan }
function Fail([string]$Text) { Write-Host ""; Write-Host "Помилка: $Text" -ForegroundColor Red; exit 1 }
function Run([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { Fail ("{0} {1} — код {2}" -f $Exe, ($Arguments -join " "), $LASTEXITCODE) }
}
function Quiet([string]$Exe, [string[]]$Arguments) {
    & $Exe @Arguments *> $null
    return ($LASTEXITCODE -eq 0)
}
function Confirm([string]$Question) {
    if ($Yes) { return $true }
    $a = Read-Host "$Question (y/n)"
    return ($a -match '^(y|yes|т|так)$')
}

# ── 1. інструменти й вхід ─────────────────────────────────────────────
Step "Git і GitHub CLI"
foreach ($t in @(@("git", "Git.Git"), @("gh", "GitHub.cli"))) {
    if (-not (Get-Command $t[0] -ErrorAction SilentlyContinue)) {
        Say ("Не знайдено {0}. Встановіть:  winget install --id {1} -e  і відкрийте нове вікно PowerShell." -f $t[0], $t[1]) Yellow
        exit 1
    }
}
if (-not (Quiet "gh" @("auth", "status", "--hostname", "github.com"))) {
    Say "Зараз відкриється браузер для входу в GitHub." Yellow
    Run "gh" @("auth", "login", "--web", "--git-protocol", "https", "--hostname", "github.com")
}
if (-not (Quiet "gh" @("repo", "view", $Repo, "--json", "name"))) {
    Fail "репозиторій $Repo не знайдено або цей акаунт не має до нього доступу."
}
$Login = (& gh api user --jq .login).Trim()
$Version = [regex]::Match([IO.File]::ReadAllText([IO.Path]::Combine($Root, "engine.py"), $Utf8), '(?m)^VERSION = "([^"]+)"').Groups[1].Value
if (-not $Version) { Fail "не вдалося прочитати VERSION з engine.py" }
Say ("Акаунт: {0}   Репозиторій: {1}   Версія: {2}" -f $Login, $Repo, $Version) Green

# ── 2. код ────────────────────────────────────────────────────────────
if (-not $NoPush) {
    Step "Код"
    if (-not (Test-Path ([IO.Path]::Combine($Root, ".git")))) { Run "git" @("init", "-b", "main") }
    if (-not (Quiet "git" @("remote", "get-url", "origin"))) {
        Run "git" @("remote", "add", "origin", "https://github.com/$Repo.git")
    }
    Run "git" @("fetch", "origin")
    if (-not (Quiet "git" @("rev-parse", "--verify", "HEAD"))) {
        # нова папка: продовжуємо історію, яка вже є на GitHub (Initial commit)
        if (Quiet "git" @("rev-parse", "--verify", "origin/main")) { Run "git" @("reset", "--mixed", "origin/main") }
    }
    if (-not (& git config user.name)) {
        $id = (& gh api user --jq .id).Trim()
        Run "git" @("config", "user.name", $Login)
        Run "git" @("config", "user.email", "$id+$Login@users.noreply.github.com")
        Say "Автор комітів: $Login (адреса GitHub без розкриття пошти)."
    }
    Run "git" @("add", "-A")
    $changed = @(& git diff --cached --name-only)
    if ($changed.Count -gt 0) {
        Say ("Змінених файлів: {0}" -f $changed.Count)
        $changed | Select-Object -First 25 | ForEach-Object { Say "  $_" DarkGray }
        if ($changed.Count -gt 25) { Say "  …" DarkGray }
        if (-not (Confirm "Закомітити й завантажити в $Repo?")) { Say "Скасовано, нічого не завантажено." Yellow; exit 0 }
        if (-not $Message) { $Message = "OptimaX $Version" }
        Run "git" @("commit", "-m", $Message)
    } else {
        Say "Нових змін немає."
    }
    Run "git" @("push", "-u", "origin", "main")
}

# ── 3. сторінка репозиторію ───────────────────────────────────────────
Step "Опис, сайт і теми"
$desc = "Windows 10/11 optimizer you can measure: a plan for your hardware, a preview of every change, before/after FPS tests and full rollback. Оптимізація Windows із замірами й повним відкатом."
$topics = "windows,windows-11,windows-10,optimizer,windows-optimization,gaming,fps,performance,tweaks,debloat,privacy,adblock,pi-hole,dns,benchmark,gpu-benchmark,pyqt6,python,ukrainian"
Run "gh" @("repo", "edit", $Repo, "--description", $desc, "--homepage", $Site, "--enable-issues", "--enable-wiki=false", "--add-topic", $topics)

Step "Мітки для issues"
$labels = [IO.File]::ReadAllText([IO.Path]::Combine($Root, ".github", "labels.json"), $Utf8) | ConvertFrom-Json
foreach ($l in $labels) {
    if (Quiet "gh" @("label", "create", $l.name, "--repo", $Repo, "--color", $l.color, "--description", $l.description, "--force")) {
        Say "  $($l.name)" DarkGray
    }
}

Step "Сайт на GitHub Pages"
if (-not (Quiet "gh" @("api", "-X", "POST", "repos/$Repo/pages", "-f", "build_type=workflow"))) {
    [void](Quiet "gh" @("api", "-X", "PUT", "repos/$Repo/pages", "-f", "build_type=workflow"))
}
if (Quiet "gh" @("workflow", "run", "pages.yml", "--repo", $Repo, "--ref", "main")) {
    Say "Сайт збирається: $Site (з'явиться за 1–2 хвилини)."
} else {
    Say "Pages увімкнено; сайт опублікується після наступного push у site/ або docs/assets/." Yellow
}

Step "Приватні звіти про вразливості"
if (Quiet "gh" @("api", "-X", "PUT", "repos/$Repo/private-vulnerability-reporting")) { Say "Увімкнено." }
else { Say "Не вдалося — увімкніть у Settings → Code security → Private vulnerability reporting." Yellow }

# ── 4. реліз із ваших файлів ──────────────────────────────────────────
if ($Release) {
    Step "Реліз v$Version"
    $out = [IO.Path]::Combine($Root, "Output")
    $setup = [IO.Path]::Combine($out, "OptimaX-Setup-$Version.exe")
    $portable = [IO.Path]::Combine($out, "OptimaX-$Version-portable.exe")
    if (-not (Test-Path $setup)) { Fail "немає $setup — спершу запустіть build_installer.bat" }
    $files = @($setup)
    if (Test-Path $portable) { $files += $portable } else { Say "Портативної версії немає (build.bat) — реліз буде без неї." Yellow }
    $files += [IO.Path]::Combine($Root, "packaging", "OptimaX-Rescue.cmd")

    $sums = foreach ($f in $files) { "{0}  {1}" -f (Get-FileHash $f -Algorithm SHA256).Hash.ToLower(), (Split-Path $f -Leaf) }
    $sumPath = [IO.Path]::Combine($out, "SHA256SUMS.txt")
    [IO.File]::WriteAllText($sumPath, (($sums -join "`n") + "`n"), $Utf8)
    $files += $sumPath
    $wg = [IO.Path]::Combine($out, "winget", $Version)
    if (Test-Path $wg) {
        $zip = [IO.Path]::Combine($out, "OptimaX-$Version-winget-manifests.zip")
        Compress-Archive -Path $wg -DestinationPath $zip -Force
        $files += $zip
    }
    $files | ForEach-Object { Say ("  {0}  ({1:N1} МБ)" -f (Split-Path $_ -Leaf), ((Get-Item $_).Length / 1MB)) DarkGray }

    $log = [IO.File]::ReadAllText([IO.Path]::Combine($Root, "CHANGELOG.md"), $Utf8)
    $m = [regex]::Match($log, "(?ms)^## \[?" + [regex]::Escape($Version) + "\]?[^\r\n]*\r?\n(.*?)(?=^## |^\[\d|\z)")
    $notes = if ($m.Success) { $m.Groups[1].Value.Trim() } else { "OptimaX $Version" }
    $notes += "`n`n---`n`n" + ('**Файли · Files:** `OptimaX-Setup-{0}.exe` — інсталятор · installer, `OptimaX-{0}-portable.exe` — без встановлення · portable, `OptimaX-Rescue.cmd` — аварійний відкат · emergency rollback. Контрольні суми · checksums: `SHA256SUMS.txt`.' -f $Version)
    $notesPath = [IO.Path]::Combine([IO.Path]::GetTempPath(), "optimax-release-notes.md")
    [IO.File]::WriteAllText($notesPath, $notes, $Utf8)

    if (Quiet "gh" @("release", "view", "v$Version", "--repo", $Repo)) {
        if (Confirm "Реліз v$Version уже є. Замінити його файли цими?") {
            Run "gh" (@("release", "upload", "v$Version") + $files + @("--repo", $Repo, "--clobber"))
        }
    } elseif (Confirm "Опублікувати реліз v$Version?") {
        Run "gh" (@("release", "create", "v$Version") + $files + @("--repo", $Repo, "--title", "OptimaX $Version", "--notes-file", $notesPath, "--target", "main"))
    }
}

# ── 5. реліз, який збирає GitHub Actions ─────────────────────────────
if ($Tag) {
    Step "Тег v$Version — реліз збере GitHub Actions"
    $remoteTag = & git ls-remote --tags origin "refs/tags/v$Version"
    if ($remoteTag) {
        Say "Тег v$Version уже є на GitHub. Для нової версії підніміть VERSION в engine.py." Yellow
    } elseif (Confirm "Поставити тег v$Version і запустити збірку релізу?") {
        if (-not (Quiet "git" @("rev-parse", "--verify", "refs/tags/v$Version"))) {
            Run "git" @("tag", "-a", "v$Version", "-m", "OptimaX $Version")
        }
        Run "git" @("push", "origin", "v$Version")
        Say "Збірка йде: https://github.com/$Repo/actions/workflows/release.yml" Green
        Say "Реліз з'явиться, коли пройдуть усі перевірки (приблизно за годину). Якщо щось упаде — реліз не опублікується, а звіт буде на сторінці запуску." Yellow
    }
}

# ── підсумок ──────────────────────────────────────────────────────────
Step "Готово"
Say "Репозиторій:  https://github.com/$Repo" Green
Say "Сайт:         $Site" Green
Say "Перевірки:    https://github.com/$Repo/actions" Green
Say ""
Say "Вручну залишилося одне: Settings → General → Social preview → Edit → Upload an image →"
Say "  docs\assets\social-preview-uk.png  (картинка для посилань у Telegram, Discord, X)."
