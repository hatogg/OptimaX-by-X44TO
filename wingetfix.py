"""
OptimaX — «Відновити winget»: winget для сторінки «Програми» і сторонніх бенчмарків без ручного встановлення.

Крок 1 (без завантаження): «Інсталятор програм» (Microsoft.DesktopAppInstaller) уже є в Windows, але не
зареєстрований для цього користувача — реєструємо його наново (Add-AppxPackage -RegisterByFamilyName).
Крок 2 (лише якщо пакета немає зовсім: LTSC, Server, видалений): офіційні файли релізу microsoft/winget-cli, які
CI кладе в реліз OptimaX (packaging/release.py winget-app), — лише звідти, із перевіркою SHA-256, у захищену папку.

Реєстрація пакета — для користувача, від імені якого працює процес. OptimaX працює з правами адміністратора: якщо
це інший обліковий запис (UAC з паролем іншого адміністратора), winget з'явився б не в того, хто сидить за ПК, —
тоді чесно кажемо про це й нічого не змінюємо. winget шукаємо лише в папці пакета (apps.winget_path), не в PATH.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import time
import zipfile

import apps as A
import engine as E
from i18n import tr

FAMILY = "Microsoft.DesktopAppInstaller_8wekyb3d8bbwe"
BUNDLE = FAMILY + ".msixbundle"  # як packaging/release.py WINGET_BUNDLE
MIN_BUILD = 17763  # winget — лише з Windows 10 1809
ARCHES = ("x64", "x86", "arm64")
ASSET_RE = re.compile(r"^OptimaX-WinGet-(\d+(?:\.\d+){1,3})\.zip$")
VERSION_RE = re.compile(r"^\d+(?:\.\d+){1,3}$")
DEP_RE = re.compile(r"^(x64|x86|arm64)/([A-Za-z0-9][A-Za-z0-9._-]{0,150}\.(?:appx|msix))$", re.I)
SID_RE = re.compile(r"^S-1-[0-9-]{1,180}$")
APPROX_MB = 300  # розмір OptimaX-WinGet-*.zip (bundle ~210 МБ + залежності) — для питання до завантаження

# Стан пакета й користувачів. Лише читання. me — користувач процесу (токен з правами адміністратора), desk — власник
# explorer.exe у цьому ж сеансі (той, хто сидить за ПК); reg — версія пакета, зареєстрованого для цього користувача;
# staged — пакет є в системі хоч для когось; prov — підготовлений для нових користувачів.
STATE_PS = (
    "$ErrorActionPreference='SilentlyContinue';"
    "function N($s){try{([Security.Principal.SecurityIdentifier]$s).Translate("
    "[Security.Principal.NTAccount]).Value}catch{''}};"
    "$me=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;"
    "$ses=(Get-Process -Id $PID).SessionId;"
    "$desk=@(Get-CimInstance Win32_Process -Filter \"Name='explorer.exe' AND SessionId=$ses\" | ForEach-Object {"
    " (Invoke-CimMethod -InputObject $_ -MethodName GetOwnerSid).Sid } | Where-Object { $_ } | Select-Object -Unique);"
    f"$reg=@(Get-AppxPackage -Name {A.WINGET_PKG} | Sort-Object {{[version]$_.Version}} -Descending);"
    f"$all=@(Get-AppxPackage -AllUsers -Name {A.WINGET_PKG});"
    f"$prov=@(Get-AppxProvisionedPackage -Online | Where-Object {{ $_.DisplayName -eq '{A.WINGET_PKG}' }});"
    "$arch=\"$([System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture)\";"
    "@{me=$me; me_name=(N $me); desk=$desk; desk_name=@($desk | ForEach-Object { N $_ });"
    " reg=$(if($reg){\"$($reg[0].Version)\"}else{''}); staged=($all.Count -gt 0); prov=($prov.Count -gt 0);"
    " arch=$arch} | ConvertTo-Json -Compress"
)
DEMO_STATE = {"me": "S-1-5-21-1-2-3-1001", "me_name": "DEMO\\user", "desk": ["S-1-5-21-1-2-3-1001"],
              "desk_name": ["DEMO\\user"], "reg": "1.29.380.0", "staged": True, "prov": True, "arch": "x64"}
DEMO_VERSION = "v1.29.380"


# ───────────────────────── стан і рішення ─────────────────────────
def _arch(x) -> str:
    a = str(x or "").strip().lower()
    return {"x64": "x64", "amd64": "x64", "x86_64": "x64", "x86": "x86", "arm64": "arm64",
            "aarch64": "arm64"}.get(a, "")


def parse_state(obj):
    """Вивід STATE_PS -> нормалізований стан або None (PowerShell нічого не дав — стан невідомий). Усе — дані:
    SID перевіряємо за шаблоном, імена лише показуємо."""
    if not isinstance(obj, dict):
        return None
    me = str(obj.get("me") or "")
    if not SID_RE.match(me):
        return None
    desk = [s for s in E.as_list(obj.get("desk")) if isinstance(s, str) and SID_RE.match(s)]
    names = [str(s)[:80] for s in E.as_list(obj.get("desk_name")) if s]
    reg = str(obj.get("reg") or "")
    return {"me": me, "me_name": str(obj.get("me_name") or "")[:80] or me, "desk": desk, "desk_name": names,
            "reg": reg if VERSION_RE.match(reg) else "", "staged": bool(obj.get("staged")),
            "prov": bool(obj.get("prov")), "arch": _arch(obj.get("arch")) or _arch(platform.machine())}


def same_user(state: dict) -> bool:
    """Чи процес OptimaX — той самий користувач, що й робочий стіл. Не вдалося дізнатися власника explorer.exe
    (інша оболонка, сеанс без робочого столу) — не забороняємо, але job пише про це в журнал."""
    return not state["desk"] or state["me"] in state["desk"]


def decide(state, build: int, wg_version: str) -> str:
    """-> unsupported | ok | unknown | other_user | register | install.
    register — пакет є в системі (зареєстрований, підготовлений чи встановлений для іншого користувача): крок 1;
    install — пакета немає зовсім: крок 2 (завантаження з релізу OptimaX)."""
    if build and build < MIN_BUILD:
        return "unsupported"
    if wg_version:
        return "ok"
    if not state:
        return "unknown"
    if not same_user(state):
        return "other_user"
    if state["reg"] or state["staged"] or state["prov"]:
        return "register"
    return "install"


def read_state():
    if not E.IS_WIN:
        return dict(DEMO_STATE)
    return parse_state(E.ps_json(STATE_PS, 60))


def winget_version() -> str:
    """Знайти winget заново (лише з папки пакета, довірений шлях) і переконатися, що він запускається:
    `winget --version` за повним шляхом. -> «v1.29.380» або ''."""
    if not E.IS_WIN:
        return DEMO_VERSION
    A._WINGET.clear()  # шлях, знайдений до реєстрації, міг застаріти
    wg = A.winget_path()
    if not wg or not os.path.isabs(wg):
        return ""
    _rc, out = E.run([wg, "--version"], 30, ro=True, enc="utf-8")
    m = re.search(r"\bv?\d+\.\d+[\w.-]*", out or "")
    return m.group(0) if m and _rc == 0 else ""


def diagnose(log=lambda *_: None) -> dict:
    """Лише читання: {"decision", "state", "version"} — для вибору, що запропонувати."""
    ver = winget_version()
    state = None if ver else read_state()
    d = decide(state, E.win_build(), ver)
    log(tr("wg.diag", what=tr(f"wg.d.{d}")))
    return {"decision": d, "state": state, "version": ver}


# ───────────────────────── команди ─────────────────────────
def register_script() -> str:
    return ("try{" + f"Add-AppxPackage -RegisterByFamilyName -MainPackage {E._psq(FAMILY)} -ErrorAction Stop;"
            "'OK'}catch{$_.Exception.Message;exit 1}")


def install_script(bundle: str, deps) -> str:
    dep = ("-DependencyPath @(" + ",".join(E._psq(p) for p in deps) + ") ") if deps else ""
    return ("try{" + f"Add-AppxPackage -Path {E._psq(bundle)} {dep}-ErrorAction Stop;"
            "'OK'}catch{$_.Exception.Message;exit 1}")


def _ps_ok(rc: int, out: str) -> bool:
    return rc == 0 and "OK" in (out or "").splitlines()[-1:]


def _verify(log, tries: int = 3) -> str:
    """winget після зміни: пакет інколи з'являється в Get-AppxPackage не одразу."""
    for i in range(tries):
        ver = winget_version()
        if ver:
            return ver
        if i < tries - 1 and E.IS_WIN:
            time.sleep(2)
    return ""


def _refuse(d: str, state) -> dict:
    """Чесна відмова без змін: непідтримувана Windows, інший користувач, невідомий стан."""
    if d == "other_user":
        msg = tr("wg.other_user", me=state["me_name"], desk=", ".join(state["desk_name"]) or "?")
    else:
        msg = tr(f"wg.d.{d}")
    return {"error": msg, "decision": d}


# ───────────────────────── крок 1: реєстрація ─────────────────────────
@E._serial
def register(log, progress=None) -> dict:
    """Крок 1: без завантаження. Повертає {"ok", "version"} або {"error"} / {"need_install": True}."""
    if progress:
        progress(0, 3, tr("wg.s_check"))
    info = diagnose(log)
    d, state = info["decision"], info["state"]
    if d == "ok":
        log(tr("wg.works", v=info["version"]))
        return {"ok": True, "version": info["version"], "decision": d}
    if d == "install":
        log(tr("wg.absent"))
        return {"need_install": True, "decision": d, "ok": False}
    if d != "register":
        return _refuse(d, state)
    if not state["desk"]:
        log(tr("wg.no_desk", me=state["me_name"]))
    if progress:
        progress(1, 3, tr("wg.s_register"))
    log(tr("wg.registering", me=state["me_name"]))
    rc, out = E.ps(register_script(), 180, log, stoppable=False)
    if E.DRY_RUN:
        return {"ok": True, "decision": d, "dry": True}
    if not _ps_ok(rc, out):
        log(tr("wg.ps_fail", err=E.first_line(out, 200) or tr("e.code", rc=rc)))
        return {"error": tr("wg.reg_fail"), "decision": d}
    if progress:
        progress(2, 3, tr("wg.s_verify"))
    ver = _verify(log)
    if not ver:
        return {"error": tr("wg.not_found_after"), "decision": d}
    log(tr("wg.works", v=ver))
    if progress:
        progress(3, 3, tr("e.finished"))
    return {"ok": True, "version": ver, "decision": d}


# ───────────────────────── крок 2: встановлення з релізу OptimaX ─────────────────────────
def find_asset(log=lambda *_: None) -> dict:
    """OptimaX-WinGet-*.zip в одному з останніх релізів OptimaX (як mining.find_asset): адреса — лише з релізу
    нашого репозиторію, ім'я — за шаблоном, сума — digest GitHub і SHA256SUMS.txt (updater.download)."""
    import updater as U
    import verify as V
    if not U.UPDATE_REPO:
        raise RuntimeError(tr("wg.no_asset"))
    rels = json.loads(U.fetch_text(f"https://api.github.com/repos/{U.UPDATE_REPO}/releases?per_page=10", 1 << 22))
    for rel in rels if isinstance(rels, list) else []:
        if not isinstance(rel, dict) or rel.get("draft"):
            continue
        assets = [a for a in rel.get("assets") or [] if isinstance(a, dict)]
        a = next((a for a in assets if ASSET_RE.match(str(a.get("name") or ""))), None)
        if not a:
            continue
        name, url = a["name"], str(a.get("browser_download_url") or "")
        if not U.asset_name_ok(name) or not U.release_url(url, name):
            continue
        sums = next((x for x in assets if x.get("name") == U.SUMS_NAME), None)
        sums_url = str(sums.get("browser_download_url") or "") if sums else ""
        return dict(name=name, url=url, size=int(a.get("size") or 0), sha256=V.digest_of(a),
                    sums_url=sums_url if U.release_url(sums_url) else "", version=ASSET_RE.match(name).group(1))
    raise RuntimeError(tr("wg.no_asset"))


def root_dir() -> str:
    """%ProgramData%\\OptimaX\\winget — захищена папка (secfs.secure_dir): звичайна програма не підмінить пакет між
    перевіркою суми й Add-AppxPackage."""
    return E.admin_dir("winget")


def _file_sha(path: str) -> str:
    return E.file_sha256(path).lower()


def verified_files(folder: str, arch: str) -> dict:
    """{"bundle": шлях, "deps": [шляхи]} — лише якщо кожен файл збігся із сумою з winget.json; інакше {}."""
    try:
        with open(os.path.join(folder, "winget.json"), encoding="utf-8") as f:
            files = (json.load(f) or {}).get("files") or {}
        if not isinstance(files, dict) or BUNDLE not in files:
            return {}
        bundle = os.path.join(folder, BUNDLE)
        if _file_sha(bundle) != str(files[BUNDLE]).lower():
            return {}
        deps = []
        for key, sha in sorted(files.items()):
            m = DEP_RE.match(key)
            if not m or m.group(1).lower() != arch:
                continue
            p = os.path.join(folder, arch, m.group(2))
            if _file_sha(p) != str(sha).lower():
                return {}
            deps.append(p)
        return {"bundle": bundle, "deps": deps}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def unpack(path: str, log) -> str:
    """Розпаковує перевірений OptimaX-WinGet-*.zip: лише bundle і залежності з відомими іменами, кожен файл — за
    сумою з winget.json. -> папка версії."""
    with zipfile.ZipFile(path) as z:
        man = json.loads(z.read("winget.json").decode("utf-8"))
        ver = str((man or {}).get("winget") or "")
        files = (man or {}).get("files") or {}
        if not VERSION_RE.match(ver) or not isinstance(files, dict) or BUNDLE not in files:
            raise RuntimeError(tr("wg.bad_file", name="winget.json"))
        root = root_dir()
        dest = os.path.join(root, ver)
        tmp = dest + ".part"
        shutil.rmtree(tmp, ignore_errors=True)
        kept = {}
        try:
            for name, sha in files.items():
                m = DEP_RE.match(str(name))
                if name == BUNDLE:
                    rel = (BUNDLE,)
                elif m:
                    rel = (m.group(1).lower(), m.group(2))
                else:
                    continue  # лише відомі імена: ні шляхів за межі папки, ні сторонніх файлів
                out = os.path.join(tmp, *rel)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                h = hashlib.sha256()
                with z.open(name) as src, open(out, "xb") as f:
                    for chunk in iter(lambda: src.read(1 << 20), b""):
                        h.update(chunk)
                        f.write(chunk)
                if h.hexdigest() != str(sha).lower():
                    raise RuntimeError(tr("wg.bad_file", name=name))
                kept["/".join(rel)] = h.hexdigest()
            with open(os.path.join(tmp, "winget.json"), "w", encoding="utf-8") as f:
                json.dump(dict(man, files=kept), f, indent=1)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    shutil.rmtree(dest, ignore_errors=True)
    os.replace(tmp, dest)
    return dest


@E._serial
def install(log, progress=None) -> dict:
    """Крок 2: пакета в системі немає — завантажити з релізу OptimaX, перевірити й встановити."""
    if progress:
        progress(0, 4, tr("wg.s_check"))
    info = diagnose(log)
    d, state = info["decision"], info["state"]
    if d == "ok":
        log(tr("wg.works", v=info["version"]))
        return {"ok": True, "version": info["version"], "decision": d}
    if d == "register":  # пакет усе ж є — завантаження не потрібне
        return register(log, progress)
    if d != "install":
        return _refuse(d, state)
    arch = state["arch"]
    if arch not in ARCHES:
        return {"error": tr("wg.arch", arch=arch or "?"), "decision": d}
    if not E.IS_WIN or E.DRY_RUN:
        log("  [dry-run] " + tr("wg.downloading", name="OptimaX-WinGet-*.zip", mb=APPROX_MB))
        log(f"  [dry-run] powershell: {install_script(BUNDLE, [])[:90]}")
        return {"ok": True, "decision": d, "dry": True}
    import updater as U
    if progress:
        progress(1, 4, tr("wg.s_download"))
    asset = find_asset(log)
    log(tr("wg.downloading", name=asset["name"], mb=f"{asset['size'] / 2**20:.0f}"))
    path = U.download(asset, log, None, publisher="")  # zip без підпису; пакети всередині підписані Microsoft
    try:
        if progress:
            progress(2, 4, tr("wg.s_unpack"))
        folder = unpack(path, log)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    got = verified_files(folder, arch)  # суми ще раз — безпосередньо перед встановленням
    if not got:
        return {"error": tr("wg.bad_file", name=os.path.basename(folder)), "decision": d}
    if not got["deps"]:
        log(tr("wg.no_deps", arch=arch))
    if progress:
        progress(3, 4, tr("wg.s_install"))
    log(tr("wg.installing", me=state["me_name"]))
    rc, out = E.ps(install_script(got["bundle"], got["deps"]), 900, log, stoppable=False)
    if not _ps_ok(rc, out):
        log(tr("wg.ps_fail", err=E.first_line(out, 200) or tr("e.code", rc=rc)))
        return {"error": tr("wg.inst_fail"), "decision": d}
    ver = _verify(log)
    if not ver:
        return {"error": tr("wg.not_found_after"), "decision": d}
    log(tr("wg.works", v=ver))
    if progress:
        progress(4, 4, tr("e.finished"))
    return {"ok": True, "version": ver, "decision": d}


# ───────────────────────── інтерфейс ─────────────────────────
def offer(main, on_done=None) -> None:
    """«Відновити winget» з кнопки (сторінка «Програми», бенчмарки): спершу стан (фоном, лише читання), потім одне
    питання саме про той крок, який потрібен. Ніколи не викликається сама — лише на дію користувача."""
    from ui_kit import Ask, RunDialog

    def finish(res):
        if on_done:
            on_done(res)

    def run(job, title):
        dlg = RunDialog(main, title, job)
        dlg.exec()
        res = dlg.res or {}
        if res.get("need_install"):
            return ask_install()
        finish(res)

    def ask_install():
        if Ask.ask(main, tr("wg.title"), tr("wg.q_install", mb=APPROX_MB), tr("wg.btn_install")):
            run(install, tr("wg.title"))
        else:
            finish({})

    def got(res):
        if not isinstance(res, dict) or res.get("error"):
            Ask.info(main, tr("wg.title"), tr("wg.d.unknown"))
            return finish({})
        d, state = res.get("decision"), res.get("state")
        if d == "ok":
            main.toast(tr("wg.works", v=res.get("version") or "").strip())
            return finish({"ok": True})
        if d in ("unsupported", "unknown", "other_user"):
            Ask.info(main, tr("wg.title"), _refuse(d, state)["error"])
            return finish({})
        if d == "register":
            if Ask.ask(main, tr("wg.title"), tr("wg.q_register", me=state["me_name"]), tr("wg.btn_register")):
                return run(register, tr("wg.title"))
            return finish({})
        ask_install()

    main.run_quick(tr("wg.title"), lambda log, p: diagnose(log), silent=True, on_done=got)
