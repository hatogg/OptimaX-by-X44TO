"""
OptimaX — «Здоров'я ПК»: одна перевірка Windows з оцінкою 0–100 і картками «гаразд / увага / проблема».

Що дивимося (лише читання; кожна картка показує команду, якою це можна перевірити самому):
• диски — стан, знос, температура, вільне місце (hardware.detect_hw);
• стабільність — сині екрани, раптові вимкнення, апаратні помилки WHEA (crashlog.analyze);
• пристрої з помилкою в Диспетчері пристроїв (dumpanalyzer.problem_devices);
• Windows Update — останнє встановлене оновлення, невдалі оновлення з кодом помилки, очікування перезавантаження,
  пауза, вимкнена служба (історія Microsoft.Update.Session, без оновлень Defender);
• захист — Defender (захист у реальному часі, вік сигнатур, останнє швидке сканування, активні загрози) або інший
  антивірус із Центру безпеки; брандмауер за профілями; UAC; SMBv1; віддалений робочий стіл без NLA; автовхід із
  паролем у реєстрі (сам пароль ніколи не читаємо — лише чи є такий параметр); автозапуск з USB і дисків;
• час — розбіжність годинника з time.windows.com і служба часу;
• звук — служби Audiosrv / AudioEndpointBuilder і активні пристрої відтворення та запису;
• час роботи без перезавантаження (з урахуванням «Швидкого запуску»).

Виправлення — лише з цього списку (FIXES). «Безпечні» (safe) можна запустити одним планом «Виправити все безпечне»:
вони нічого не вимикають і не ламають (оновити сигнатури, сканування, синхронізувати час, пошук нового обладнання,
перезапуск звуку, увімкнути захист у реальному часі). Решта — окремою кнопкою з поясненням ризику. Кожна зміна
налаштувань іде через журнал відкату OptimaX (E.apply_tweaks), тож її повертає сторінка «Резервні копії» і
OptimaX-Rescue.cmd. Після виправлення перевіряємо знову й кажемо чесно: «виправлено», «досі проблема», «не вдалося»
або «після перезавантаження».
"""
from __future__ import annotations

import ctypes
import re
import shutil
import time

import engine as E
from i18n import tr

OK, INFO, WARN, BAD, UNKNOWN = "ok", "info", "warn", "bad", "unknown"
ORDER = {BAD: 0, WARN: 1, UNKNOWN: 2, INFO: 3, OK: 4}
PENALTY = {BAD: 20, WARN: 7}

# порядок карток за однакового стану
CHECKS = ("disk", "stability", "devices", "wu", "defender", "firewall", "uac", "smb1", "rdp", "autologon", "time",
          "audio", "uptime", "autorun")
PS_CHECKS = {"wu", "defender", "firewall", "uac", "smb1", "rdp", "autologon", "time", "audio", "uptime", "autorun"}

# ── межі (одна межа — одне число; причина поруч) ──
DISK_FREE_BAD_GB = 10  # менше — Windows не встановить оновлення, ігри не оновляться, файл підкачки не виросте
DISK_FREE_WARN_GB = 25
DISK_FREE_WARN_PCT = 10
DISK_WEAR_WARN = 80  # % ресурсу записів SSD
DISK_TEMP_WARN = 70  # °C — SSD починає скидати швидкість
WU_WARN_DAYS = 40  # місячне оновлення пропущено
WU_BAD_DAYS = 70  # пропущено два й більше — відомі діри відкриті
DEF_SIG_WARN = 7  # днів без оновлення сигнатур
DEF_SIG_BAD = 14
DEF_SCAN_WARN = 30  # днів без швидкого сканування
TIME_WARN_S = 60  # більше хвилини — сайти, лаунчери й двофакторні коди починають відмовляти
TIME_BAD_S = 300  # 5 хвилин — межа Kerberos, HTTPS-сертифікати «ще не дійсні»
UPTIME_WARN_DAYS = 7
CRASH_RECENT_DAYS = 7
POWER_LOSS_WARN = 3
NEVER = 4294967295  # QuickScanAge, якщо сканування не було ніколи

# Критичні класи пристроїв: без них немає зображення, диска чи мережі
CRITICAL_CLASSES = {"display", "diskdrive", "net", "scsiadapter", "hdc", "system"}
DEV_SKIP = {22, 45}  # 22 — вимкнено вручну, 45 — зараз не під'єднаний
DEV_CODES = (1, 3, 10, 12, 14, 18, 19, 21, 24, 28, 31, 32, 37, 39, 40, 41, 43, 48, 52)

# Оновлення Defender пишуться в ту саму історію щодня — вони не про оновлення Windows
DEFENDER_UPDATE = re.compile(r"defender|security intelligence|antivirus|kb2267602|kb4052623|kb915597", re.I)

# ───────────────────────── збір фактів (лише читання) ─────────────────────────
# Кожен блок — окремий try: зламаний WMI-клас, вимкнений Defender чи відсутній модуль не мають зупиняти решту.
FACTS_PS = r"""
$r=@{}
function T([scriptblock]$b){ try { & $b } catch { $null } }
$r.wuhist = T {
  $se=New-Object -ComObject Microsoft.Update.Session
  $hs=$se.CreateUpdateSearcher()
  $n=$hs.GetTotalHistoryCount()
  if($n -le 0){ ,@() } else {
    ,@($hs.QueryHistory(0,[Math]::Min($n,150)) | Where-Object { $_.Operation -eq 1 } | ForEach-Object {
      @{t=[string]$_.Title; rc=[int]$_.ResultCode; hr=('0x{0:X8}' -f [int]$_.HResult);
        ts=([DateTimeOffset][DateTime]::SpecifyKind($_.Date,'Utc')).ToUnixTimeSeconds()} })
  }
}
$r.hotfix = T { Get-HotFix -ErrorAction Stop | Where-Object { $_.InstalledOn } | Sort-Object InstalledOn -Descending |
  Select-Object -First 1 | ForEach-Object { ([DateTimeOffset]$_.InstalledOn).ToUnixTimeSeconds() } }
$r.wureboot = (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired') -or
  (Test-Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending')
$r.wusvc = T { "$((Get-Service wuauserv -ErrorAction Stop).StartType)" }
$r.wupause = T { [string](Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -ErrorAction Stop).PauseUpdatesExpiryTime }
$mp = T { Get-MpComputerStatus -ErrorAction Stop }
if($mp){ $r.mp=@{svc=[bool]$mp.AMServiceEnabled; av=[bool]$mp.AntivirusEnabled; rtp=[bool]$mp.RealTimeProtectionEnabled;
  sig=[long]$mp.AntivirusSignatureAge; quick=[long]$mp.QuickScanAge; mode=[string]$mp.AMRunningMode} }
$r.threats = T { @(Get-MpThreat -ErrorAction Stop | Where-Object { $_.IsActive }).Count }
$dp='HKLM:\SOFTWARE\Policies\Microsoft\Windows Defender'
$r.defpol = @{as=(T { (Get-ItemProperty $dp -ErrorAction Stop).DisableAntiSpyware });
  rtp=(T { (Get-ItemProperty "$dp\Real-Time Protection" -ErrorAction Stop).DisableRealtimeMonitoring })}
$r.avs = T { ,@(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct -ErrorAction Stop |
  ForEach-Object { @{n=[string]$_.displayName; s=[long]$_.productState} }) }
$r.fws = T { ,@(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName FirewallProduct -ErrorAction Stop |
  ForEach-Object { @{n=[string]$_.displayName; s=[long]$_.productState} }) }
$r.fw = T { ,@(Get-NetFirewallProfile -PolicyStore ActiveStore -ErrorAction Stop |
  ForEach-Object { @{n=[string]$_.Name; on=([string]$_.Enabled -eq 'True')} }) }
$fp='HKLM:\SOFTWARE\Policies\Microsoft\WindowsFirewall'
$r.fwpol = [bool](T { @('DomainProfile','PrivateProfile','PublicProfile','StandardProfile') |
  Where-Object { $null -ne (Get-ItemProperty "$fp\$_" -ErrorAction SilentlyContinue).EnableFirewall } })
$sy = T { Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -ErrorAction Stop }
$r.uac = @{lua=$sy.EnableLUA; cpa=$sy.ConsentPromptBehaviorAdmin}
$r.smb1srv = T { [bool](Get-SmbServerConfiguration -ErrorAction Stop).EnableSMB1Protocol }
$r.smb1cli = T { (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Services\mrxsmb10' -ErrorAction Stop).Start }
$ts = T { Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -ErrorAction Stop }
$rt = T { Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -ErrorAction Stop }
$r.rdp = @{deny=$ts.fDenyTSConnections; nla=$rt.UserAuthentication;
  pol=(T { (Get-ItemProperty 'HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services' -ErrorAction Stop).UserAuthentication })}
$wl = T { Get-Item 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon' -ErrorAction Stop }
if($wl){ $r.autologon=@{on=[string]$wl.GetValue('AutoAdminLogon'); pwd=($wl.GetValueNames() -contains 'DefaultPassword')} }
$ex='SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer'
$r.autorun = @{lm=(T { (Get-ItemProperty "HKLM:\$ex" -ErrorAction Stop).NoDriveTypeAutoRun });
  cu=(T { (Get-ItemProperty "HKCU:\$ex" -ErrorAction Stop).NoDriveTypeAutoRun });
  ap=(T { (Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers' -ErrorAction Stop).DisableAutoplay })}
$w = T { Get-Service W32Time -ErrorAction Stop }
$r.timesvc = @{st=[string]$w.Status; start=[string]$w.StartType}
$mm='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio'
function Act($k){ T { @(Get-ChildItem "$mm\$k" -ErrorAction Stop | Where-Object { (Get-ItemProperty $_.PSPath).DeviceState -eq 1 }).Count } }
$r.audio = @{srv=(T { [string](Get-Service Audiosrv -ErrorAction Stop).Status });
  aeb=(T { [string](Get-Service AudioEndpointBuilder -ErrorAction Stop).Status }); out=(Act 'Render'); inp=(Act 'Capture')}
$r.hiberboot = T { (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -ErrorAction Stop).HiberbootEnabled }
$r | ConvertTo-Json -Compress -Depth 5
"""

TIME_RE = re.compile(r"([+-]\d+(?:[.,]\d+)?)s\b")


def _now() -> int:
    return int(time.time())


def uptime_s() -> int:
    if not E.IS_WIN:
        return {"gaming": 9, "laptop": 2, "old": 23}.get(E.DEMO, 1) * 86400 + 3600
    try:
        return int(ctypes.windll.kernel32.GetTickCount64() // 1000)
    except Exception:
        return -1


def time_offset():
    """Розбіжність годинника з time.windows.com у секундах (медіана 3 замірів) або None, якщо сервер не відповів."""
    if not E.IS_WIN:
        return {"old": -412.5}.get(E.DEMO, 0.8)
    rc, out = E.run(["w32tm", "/stripchart", "/computer:time.windows.com", "/dataonly", "/samples:3"], 30, ro=True)
    vals = []
    for m in TIME_RE.finditer(out or ""):
        try:
            vals.append(float(m.group(1).replace(",", ".")))
        except ValueError:
            pass
    if not vals:
        return None
    vals.sort()
    return round(vals[len(vals) // 2], 2)


def disk_facts(hw: dict) -> list:
    out = []
    for d in (hw or {}).get("disks") or []:
        free = []
        for L in d.get("letters") or []:
            L = str(L).strip(":\\ ")[:1].upper()
            if not L:
                continue
            if E.IS_WIN:
                try:
                    u = shutil.disk_usage(f"{L}:\\")
                    free.append(dict(l=L, free=round(u.free / 1e9, 1), total=round(u.total / 1e9, 1)))
                except OSError:
                    continue
            else:
                demo_free = {"C": {"old": 7.2, "laptop": 41.0}.get(E.DEMO, 182.4), "D": 912.0}.get(L, 300.0)
                free.append(dict(l=L, free=demo_free, total=float(d.get("size_gb") or 1000)))
        out.append(dict(name=d.get("name") or "?", health=d.get("health"), wear=d.get("wear"), temp=d.get("temp"),
                        media=d.get("media"), free=free))
    return out


DAY = 86400
DEMO_PS = {
    "gaming": dict(
        wuhist=[dict(t="2026-10 Cumulative Update for Windows 11 Version 24H2 for x64-based Systems (KB5066835)", rc=2,
                     hr="0x00000000", ts=-12 * DAY),
                dict(t="Security Intelligence Update for Microsoft Defender Antivirus - KB2267602", rc=2,
                     hr="0x00000000", ts=-1 * DAY)],
        wureboot=True, wusvc="Manual", wupause="",
        mp=dict(svc=True, av=True, rtp=True, sig=9, quick=3, mode="Normal"), threats=0, defpol={},
        avs=[dict(n="Windows Defender", s=397568)], fws=[], fw=[dict(n="Domain", on=True), dict(n="Private", on=True),
                                                               dict(n="Public", on=True)], fwpol=False,
        uac=dict(lua=1, cpa=5), smb1srv=False, smb1cli=3, rdp=dict(deny=1, nla=1), autologon=dict(on="0", pwd=False),
        autorun=dict(lm=None, cu=None, ap=0), timesvc=dict(st="Stopped", start="Manual"),
        audio=dict(srv="Running", aeb="Running", out=2, inp=1), hiberboot=1),
    "old": dict(
        wuhist=[dict(t="2026-07 Cumulative Update for Windows 10 Version 22H2 for x64-based Systems (KB5062554)", rc=2,
                     hr="0x00000000", ts=-104 * DAY),
                dict(t="2026-10 Cumulative Update for Windows 10 Version 22H2 for x64-based Systems (KB5066791)", rc=4,
                     hr="0x800F0922", ts=-6 * DAY)],
        wureboot=False, wusvc="Manual", wupause="",
        mp=dict(svc=True, av=True, rtp=False, sig=19, quick=NEVER, mode="Normal"), threats=0, defpol={},
        avs=[dict(n="Windows Defender", s=393472)], fws=[], fw=[dict(n="Domain", on=True), dict(n="Private", on=True),
                                                               dict(n="Public", on=False)], fwpol=False,
        uac=dict(lua=1, cpa=0), smb1srv=True, smb1cli=2, rdp=dict(deny=0, nla=0),
        autologon=dict(on="1", pwd=True), autorun=dict(lm=None, cu=None, ap=0),
        timesvc=dict(st="Stopped", start="Disabled"), audio=dict(srv="Stopped", aeb="Running", out=1, inp=0),
        hiberboot=1),
}
DEMO_PS["laptop"] = dict(DEMO_PS["gaming"], wureboot=False, mp=dict(DEMO_PS["gaming"]["mp"], sig=1), smb1cli=None,
                         audio=dict(srv="Running", aeb="Running", out=1, inp=2))
DEMO_FIXED: set = set()  # демо: що «виправлено» в цьому сеансі — повторна перевірка має це побачити


def _demo_ps() -> dict:
    now = _now()
    base = DEMO_PS.get(E.DEMO, DEMO_PS["gaming"])
    f = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    f["wuhist"] = [dict(e, ts=now + e["ts"]) for e in base["wuhist"]]
    fx = DEMO_FIXED
    if "def_sig" in fx:
        f["mp"]["sig"] = 0
    if "def_scan" in fx:
        f["mp"]["quick"] = 0
    if "def_rtp" in fx:
        f["mp"]["rtp"] = True
    if "fw_on" in fx:
        f["fw"] = [dict(x, on=True) for x in f["fw"]]
    if "uac_on" in fx:
        f["uac"] = dict(lua=1, cpa=5)
    if "rdp_nla" in fx:
        f["rdp"] = dict(f["rdp"], nla=1)
    if "autologon_off" in fx:
        f["autologon"] = dict(on="0", pwd=False)
    if "autorun_off" in fx:
        f["autorun"] = dict(f["autorun"], lm=255, ap=1)
    if "time_svc" in fx:
        f["timesvc"] = dict(st="Running", start="Manual")
    if "audio_restart" in fx:
        f["audio"] = dict(f["audio"], srv="Running", aeb="Running")
    return f


def collect(hw: dict, only=None, log=lambda *_: None) -> dict:
    """Факти для перевірок (усі або лише only). Лише читання."""
    want = set(only or CHECKS)
    facts: dict = dict(ts=_now(), admin=bool(E.is_admin()) if E.IS_WIN else True, only=sorted(want))
    if want & PS_CHECKS:
        log(tr("hc.log.system"))
        data = E.ps_json(FACTS_PS, 120) if E.IS_WIN else _demo_ps()
        facts["ps"] = data if isinstance(data, dict) else None
    if "time" in want:
        log(tr("hc.log.time"))
        off = time_offset()
        if not E.IS_WIN and "time_sync" in DEMO_FIXED:
            off = 0.3
        facts["offset"] = off
    if "uptime" in want:
        facts["uptime"] = uptime_s()
    if "devices" in want:
        log(tr("hc.log.devices"))
        import dumpanalyzer as DA
        devs = DA.problem_devices()
        if not E.IS_WIN and "dev_scan" in DEMO_FIXED:
            devs = []
        facts["devices"] = devs
    if "disk" in want:
        facts["disks"] = disk_facts(hw)
    if "stability" in want:
        log(tr("hc.log.stability"))
        import crashlog as CL
        try:
            facts["crash"] = CL.analyze(sessions=None, mining=bool((hw or {}).get("mining_gpu")))
        except Exception as e:  # журнал подій недоступний — картка «не вдалося перевірити»
            log(f"  ⚠ {type(e).__name__}: {e}")
            facts["crash"] = None
    return facts


# ───────────────────────── оцінка ─────────────────────────
def _card(cid: str, st: str, head: str, **kw) -> dict:
    """head / det — ключі перекладу з підстановками: зберігаються так, щоб картка перекладалася під час показу."""
    return dict(id=cid, st=st, head=[head, kw.pop("p", {})], det=kw.pop("det", []), fixes=kw.pop("fixes", []),
                opens=kw.pop("opens", []))


def _d(key: str, **p) -> list:
    return [key, p]


def _on(product_state) -> bool:
    """productState Центру безпеки: біти 12–15 — стан (1 — увімкнено)."""
    try:
        return (int(product_state) >> 12) & 0xF == 1
    except (TypeError, ValueError):
        return False


def _date(ts) -> str:
    return time.strftime("%d.%m.%Y", time.localtime(int(ts or 0)))


def _pause_until(s) -> int:
    """PauseUpdatesExpiryTime ("2026-12-01T10:00:00Z") -> unix або 0."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", str(s or ""))
    if not m:
        return 0
    import calendar
    return calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0))


def check_disk(f: dict) -> dict:
    disks = f.get("disks")
    if not disks:
        return _card("disk", UNKNOWN, "hc.disk.na")
    st, det, opens = OK, [], []
    for d in disks:
        h = str(d.get("health") or "").strip().lower()
        if h and h not in ("healthy", "ok"):
            st = BAD
            det.append(_d("hc.disk.health", name=d["name"], health=d.get("health")))
            opens.append(["hwc", "storage"])
        if isinstance(d.get("wear"), (int, float)) and d["wear"] >= DISK_WEAR_WARN:
            st = st if st == BAD else WARN
            det.append(_d("hc.disk.wear", name=d["name"], n=int(d["wear"])))
            opens.append(["hwc", "storage"])
        if isinstance(d.get("temp"), (int, float)) and d["temp"] > DISK_TEMP_WARN:
            st = st if st == BAD else WARN
            det.append(_d("hc.disk.temp", name=d["name"], t=int(d["temp"])))
        for v in d.get("free") or []:
            pct = 100.0 * v["free"] / v["total"] if v.get("total") else 100.0
            if v["free"] < DISK_FREE_BAD_GB:
                st = BAD
            elif v["free"] < DISK_FREE_WARN_GB or pct < DISK_FREE_WARN_PCT:
                st = st if st == BAD else WARN
            else:
                det.append(_d("hc.disk.free_ok", l=v["l"], free=f"{v['free']:.0f}", total=f"{v['total']:.0f}"))
                continue
            det.append(_d("hc.disk.free_low", l=v["l"], free=f"{v['free']:.1f}", total=f"{v['total']:.0f}"))
            opens.append(["page", "cleanup"])
    head = {OK: "hc.disk.ok", WARN: "hc.disk.warn", BAD: "hc.disk.bad"}[st]
    return _card("disk", st, head, p=dict(n=len(disks)), det=det, opens=_uniq(opens))


def check_stability(f: dict) -> dict:
    res = f.get("crash")
    if not isinstance(res, dict):
        return _card("stability", UNKNOWN, "hc.stab.na", opens=[["crash", ""]])
    now = f.get("ts") or _now()
    incs = res.get("incidents") or []
    bsod = [i for i in incs if i.get("kind") == "bsod"]
    recent = [i for i in bsod if now - int(i.get("ts") or 0) <= CRASH_RECENT_DAYS * DAY]
    power = [i for i in incs if i.get("kind") == "power"]
    w = res.get("whea") or {}
    g = res.get("gpu") or {}
    m = res.get("memtest") or {}
    st, det = OK, []
    if bsod:
        det.append(_d("hc.stab.bsod", n=len(bsod), days=res.get("days", 30), last=_date(max(i["ts"] for i in bsod))))
        st = BAD if recent or len(bsod) >= 2 else WARN
    if len(power) >= POWER_LOSS_WARN:
        det.append(_d("hc.stab.power", n=len(power), days=res.get("days", 30)))
        st = st if st == BAD else WARN
    elif power:
        det.append(_d("hc.stab.power", n=len(power), days=res.get("days", 30)))
    if w:
        det.append(_d("hc.stab.whea", n=w.get("n", 0)))
        st = BAD if w.get("fatal") else (st if st == BAD else WARN)
    if g and int(g.get("n") or 0) >= 3:
        det.append(_d("hc.stab.tdr", n=g["n"]))
        st = st if st == BAD else WARN
    if m and m.get("ok") is False:
        det.append(_d("hc.stab.mem"))
        st = BAD
    head = {OK: "hc.stab.ok", WARN: "hc.stab.warn", BAD: "hc.stab.bad"}[st]
    return _card("stability", st, head, p=dict(days=res.get("days", 30)), det=det,
                 opens=[["crash", ""]] if st != OK else [])


def check_devices(f: dict) -> dict:
    devs = f.get("devices")
    if devs is None:
        return _card("devices", UNKNOWN, "hc.dev.na")
    bad = [d for d in devs if int(d.get("code") or 0) not in DEV_SKIP]
    off = [d for d in devs if int(d.get("code") or 0) == 22]
    det = []
    for d in bad[:6]:
        code = int(d.get("code") or 0)
        det.append(_d("hc.dev.item", name=str(d.get("name") or "?")[:70], code=code,
                      why=tr(f"hc.dev.c{code}") if code in DEV_CODES else tr("hc.dev.cx")))
    if off:
        det.append(_d("hc.dev.disabled", n=len(off)))
    if not bad:
        return _card("devices", OK, "hc.dev.ok", det=det)
    crit = any(str(d.get("cls") or "").lower() in CRITICAL_CLASSES for d in bad)
    return _card("devices", BAD if crit else WARN, "hc.dev.bad", p=dict(n=len(bad)), det=det,
                 fixes=["dev_scan"], opens=[["settings", "devmgmt.msc"]])


def check_wu(f: dict) -> dict:
    ps = f.get("ps") or {}
    now = f.get("ts") or _now()
    hist = ps.get("wuhist")
    last_ok = None
    failed = []
    if isinstance(hist, list):
        win = [e for e in hist if isinstance(e, dict) and not DEFENDER_UPDATE.search(str(e.get("t") or ""))]
        oks = [int(e.get("ts") or 0) for e in win if int(e.get("rc") or 0) in (2, 3)]
        last_ok = max(oks) if oks else None
        for e in win:
            if int(e.get("rc") or 0) in (4, 5) and now - int(e.get("ts") or 0) <= 30 * DAY:
                later = any(x.get("t") == e.get("t") and int(x.get("rc") or 0) in (2, 3)
                            and int(x.get("ts") or 0) > int(e.get("ts") or 0) for x in win)
                if not later and e.get("t") not in [x.get("t") for x in failed]:
                    failed.append(e)
    if last_ok is None and isinstance(ps.get("hotfix"), (int, float)):
        last_ok = int(ps["hotfix"])
    svc_off = str(ps.get("wusvc") or "").lower() == "disabled"
    pause = _pause_until(ps.get("wupause"))
    paused = pause > now
    if last_ok is None and not failed and not svc_off and not paused:
        return _card("wu", UNKNOWN, "hc.wu.na", opens=[["settings", "ms-settings:windowsupdate"]])
    st, det, fixes = OK, [], []
    days = (now - last_ok) // DAY if last_ok else None
    if days is not None:
        det.append(_d("hc.wu.last", date=_date(last_ok), n=days))
        if days > WU_BAD_DAYS:
            st = BAD
        elif days > WU_WARN_DAYS:
            st = WARN
    if failed:
        e = failed[0]
        det.append(_d("hc.wu.failed", n=len(failed), code=e.get("hr") or "?", title=str(e.get("t") or "")[:90]))
        st = st if st == BAD else WARN
        fixes.append("wu_reset")
    if ps.get("wureboot"):
        det.append(_d("hc.wu.reboot"))
        st = st if st == BAD else WARN
    if svc_off:
        det.append(_d("hc.wu.svc_off"))
        st = st if st == BAD else WARN
    if paused:
        det.append(_d("hc.wu.paused", date=_date(pause)))
        if E.JOURNAL.has("wu_pause"):
            det.append(_d("hc.wu.paused_by_us"))
        st = INFO if st == OK else st
    head = {OK: "hc.wu.ok", INFO: "hc.wu.info", WARN: "hc.wu.warn", BAD: "hc.wu.bad"}[st]
    opens = [["settings", "ms-settings:windowsupdate"]]
    if paused and E.JOURNAL.has("wu_pause"):
        opens.append(["page", "backup"])
    return _card("wu", st, head, det=det, fixes=fixes, opens=opens)


def third_party(products) -> list:
    return [p.get("n") for p in products or [] if isinstance(p, dict) and _on(p.get("s"))
            and "defender" not in str(p.get("n") or "").lower()]


def check_defender(f: dict) -> dict:
    ps = f.get("ps") or {}
    others = third_party(ps.get("avs"))
    opens = [["settings", "windowsdefender:"]]
    if others:
        return _card("defender", OK, "hc.def.other", p=dict(name=", ".join(others)[:60]))
    mp = ps.get("mp")
    pol = ps.get("defpol") or {}
    if pol.get("as") == 1 or pol.get("rtp") == 1:
        det = [_d("hc.def.policy")]
        if E.JOURNAL.has("disable_defender"):
            det.append(_d("hc.def.policy_ours"))
            opens.append(["page", "backup"])
        return _card("defender", BAD, "hc.def.off", det=det, opens=opens)
    if not isinstance(mp, dict):
        if any(_on(p.get("s")) for p in ps.get("avs") or [] if isinstance(p, dict)):
            return _card("defender", OK, "hc.def.ok_sc")
        return _card("defender", UNKNOWN, "hc.def.na", opens=opens)
    st, det, fixes = OK, [], []
    if not mp.get("rtp") or not mp.get("av"):
        st = BAD
        det.append(_d("hc.def.rtp_off"))
        fixes.append("def_rtp")
    sig = int(mp.get("sig") if mp.get("sig") is not None else -1)
    if sig > DEF_SIG_BAD:
        st = BAD
    elif sig > DEF_SIG_WARN:
        st = st if st == BAD else WARN
    if sig > DEF_SIG_WARN:
        det.append(_d("hc.def.sig_old", n=sig))
        fixes.append("def_sig")
    elif sig >= 0:
        det.append(_d("hc.def.sig_ok", n=sig))
    q = int(mp.get("quick") if mp.get("quick") is not None else -1)
    if q >= NEVER or q > DEF_SCAN_WARN:
        st = st if st == BAD else WARN
        det.append(_d("hc.def.scan_never") if q >= NEVER else _d("hc.def.scan_old", n=q))
        fixes.append("def_scan")
    th = ps.get("threats")
    if isinstance(th, int) and th > 0:
        st = BAD
        det.append(_d("hc.def.threats", n=th))
        opens.append(["settings", "windowsdefender://threat"])
    if mp.get("rtp") and not E.JOURNAL.has("defender_limit"):
        # Defender гальмує ігри — відповідь не «вимкнути», а обмежити: наявна зміна каталогу (з відкатом)
        det.append(_d("hc.def.limit_hint"))
        opens.append(["tweak", "defender_limit"])
    head = {OK: "hc.def.ok", WARN: "hc.def.warn", BAD: "hc.def.bad"}[st]
    return _card("defender", st, head, det=det, fixes=fixes, opens=opens)


FW_PROFILES = {"domain": "domainprofile", "private": "privateprofile", "public": "publicprofile"}


def fw_off(ps: dict) -> list:
    return [str(p.get("n") or "").lower() for p in ps.get("fw") or []
            if isinstance(p, dict) and not p.get("on") and str(p.get("n") or "").lower() in FW_PROFILES]


def check_firewall(f: dict) -> dict:
    ps = f.get("ps") or {}
    others = third_party(ps.get("fws"))
    if others:
        return _card("firewall", OK, "hc.fw.other", p=dict(name=", ".join(others)[:60]))
    if not isinstance(ps.get("fw"), list) or not ps["fw"]:
        return _card("firewall", UNKNOWN, "hc.fw.na")
    off = fw_off(ps)
    if not off:
        return _card("firewall", OK, "hc.fw.ok")
    names = ", ".join(tr(f"hc.fw.p.{p}") for p in off)
    st = BAD if "public" in off else WARN
    det = [_d("hc.fw.policy")] if ps.get("fwpol") else []
    return _card("firewall", st, "hc.fw.off", p=dict(names=names), det=det,
                 fixes=[] if ps.get("fwpol") else ["fw_on"], opens=[["settings", "windowsdefender://network"]])


def check_uac(f: dict) -> dict:
    u = (f.get("ps") or {}).get("uac") or {}
    if not f.get("ps"):
        return _card("uac", UNKNOWN, "hc.uac.na")
    if u.get("lua") == 0:
        return _card("uac", BAD, "hc.uac.off", fixes=["uac_on"])
    if u.get("cpa") == 0:
        return _card("uac", WARN, "hc.uac.silent", fixes=["uac_on"])
    return _card("uac", OK, "hc.uac.ok")


def smb1_on(ps: dict) -> bool:
    cli = ps.get("smb1cli")
    return ps.get("smb1srv") is True or (isinstance(cli, int) and cli != 4)


def check_smb1(f: dict) -> dict:
    ps = f.get("ps")
    if not ps:
        return _card("smb1", UNKNOWN, "hc.smb1.na")
    if smb1_on(ps):
        return _card("smb1", WARN, "hc.smb1.on", fixes=["smb1_off"])
    return _card("smb1", OK, "hc.smb1.ok")


def check_rdp(f: dict) -> dict:
    ps = f.get("ps")
    if not ps:
        return _card("rdp", UNKNOWN, "hc.rdp.na")
    r = ps.get("rdp") or {}
    if r.get("deny") != 0:
        return _card("rdp", OK, "hc.rdp.off")
    if r.get("nla") == 0:
        det = [_d("hc.rdp.policy")] if r.get("pol") is not None else []
        return _card("rdp", BAD, "hc.rdp.no_nla", det=det, fixes=[] if det else ["rdp_nla"])
    return _card("rdp", INFO, "hc.rdp.on")


def check_autologon(f: dict) -> dict:
    ps = f.get("ps")
    if not ps:
        return _card("autologon", UNKNOWN, "hc.al.na")
    a = ps.get("autologon") or {}
    if str(a.get("on") or "").strip() == "1":
        if a.get("pwd"):
            return _card("autologon", WARN, "hc.al.pwd", fixes=["autologon_off"])
        return _card("autologon", INFO, "hc.al.on")
    return _card("autologon", OK, "hc.al.ok")


def autorun_off(ps: dict) -> bool:
    a = ps.get("autorun") or {}
    return a.get("lm") == 255 or a.get("cu") == 255 or a.get("ap") == 1


def check_autorun(f: dict) -> dict:
    ps = f.get("ps")
    if not ps:
        return _card("autorun", UNKNOWN, "hc.ar.na")
    if autorun_off(ps):
        return _card("autorun", OK, "hc.ar.ok")
    return _card("autorun", INFO, "hc.ar.on", fixes=["autorun_off"])


def check_time(f: dict) -> dict:
    ps = f.get("ps") or {}
    svc = ps.get("timesvc") or {}
    disabled = str(svc.get("start") or "").lower() == "disabled"
    off = f.get("offset")
    st, det, fixes = OK, [], []
    if disabled:
        st = WARN
        det.append(_d("hc.time.svc_off"))
        fixes.append("time_svc")
    if off is None:
        det.append(_d("hc.time.no_server"))
        st = st if st != OK else UNKNOWN
    else:
        a = abs(float(off))
        det.append(_d("hc.time.offset", s=f"{off:+.1f}"))
        if a > TIME_BAD_S:
            st = BAD
        elif a > TIME_WARN_S:
            st = st if st == BAD else WARN
        if a > TIME_WARN_S and not disabled:
            fixes.append("time_sync")
    head = {OK: "hc.time.ok", UNKNOWN: "hc.time.na", WARN: "hc.time.warn", BAD: "hc.time.bad"}[st]
    return _card("time", st, head, det=det, fixes=fixes, opens=[["settings", "ms-settings:dateandtime"]])


def check_audio(f: dict) -> dict:
    ps = f.get("ps")
    if not ps:
        return _card("audio", UNKNOWN, "hc.au.na")
    a = ps.get("audio") or {}
    stopped = [n for n, k in (("Audiosrv", "srv"), ("AudioEndpointBuilder", "aeb"))
               if a.get(k) is not None and str(a.get(k)).lower() != "running"]
    det, st, fixes = [], OK, []
    if stopped:
        st = BAD
        det.append(_d("hc.au.stopped", names=", ".join(stopped)))
        fixes.append("audio_restart")
    if a.get("out") == 0:
        st = st if st == BAD else WARN
        det.append(_d("hc.au.no_out"))
    elif isinstance(a.get("out"), int):
        det.append(_d("hc.au.devs", out=a["out"], inp=a.get("inp") if isinstance(a.get("inp"), int) else "?"))
    head = {OK: "hc.au.ok", WARN: "hc.au.warn", BAD: "hc.au.bad"}[st]
    return _card("audio", st, head, det=det, fixes=fixes, opens=[["settings", "ms-settings:sound"]])


def check_uptime(f: dict) -> dict:
    up = f.get("uptime")
    if not isinstance(up, int) or up < 0:
        return _card("uptime", UNKNOWN, "hc.up.na")
    days = up // DAY
    if days < UPTIME_WARN_DAYS:
        return _card("uptime", OK, "hc.up.ok", p=dict(n=days))
    det = [_d("hc.up.fast")] if (f.get("ps") or {}).get("hiberboot") == 1 else []
    return _card("uptime", WARN, "hc.up.long", p=dict(n=days), det=det)


CHECK_FN = {"disk": check_disk, "stability": check_stability, "devices": check_devices, "wu": check_wu,
            "defender": check_defender, "firewall": check_firewall, "uac": check_uac, "smb1": check_smb1,
            "rdp": check_rdp, "autologon": check_autologon, "time": check_time, "audio": check_audio,
            "uptime": check_uptime, "autorun": check_autorun}

# Команда лише для читання, якою можна перевірити картку самому (PowerShell)
CHECK_CMD = {
    "disk": "Get-PhysicalDisk | Select FriendlyName, HealthStatus; Get-Volume",
    "stability": "Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,1001,6008} -MaxEvents 20",
    "devices": "Get-PnpDevice -PresentOnly | Where Status -eq Error | Select FriendlyName, Class, ConfigManagerErrorCode",
    "wu": "(New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher().QueryHistory(0,20) | "
          "Select Date, Title, ResultCode, HResult",
    "defender": "Get-MpComputerStatus | Select RealTimeProtectionEnabled, AntivirusSignatureAge, QuickScanAge",
    "firewall": "Get-NetFirewallProfile -PolicyStore ActiveStore | Select Name, Enabled",
    "uac": "Get-ItemProperty HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System | "
           "Select EnableLUA, ConsentPromptBehaviorAdmin",
    "smb1": "Get-SmbServerConfiguration | Select EnableSMB1Protocol",
    "rdp": "Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' | Select fDenyTSConnections",
    "autologon": "(Get-Item 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Winlogon').GetValueNames()",
    "time": "w32tm /stripchart /computer:time.windows.com /dataonly /samples:3",
    "audio": "Get-Service Audiosrv, AudioEndpointBuilder",
    "uptime": "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime",
    "autorun": "Get-ItemProperty HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\AutoplayHandlers",
}


# Кнопки «відкрити» на картках (нічого не змінюють): значення з opens -> ключ підпису
OPEN_LABEL = {"ms-settings:windowsupdate": "hc.o.wu", "windowsdefender:": "hc.o.sec",
              "windowsdefender://threat": "hc.o.threat", "windowsdefender://network": "hc.o.fw",
              "devmgmt.msc": "hc.o.devmgr", "ms-settings:dateandtime": "hc.o.time", "ms-settings:sound": "hc.o.sound",
              "defender_limit": "hc.o.def_limit", "cleanup": "hc.o.cleanup", "backup": "hc.o.backup", "storage": "hc.o.storage", "crash": "hc.o.crash"}


def _uniq(items: list) -> list:
    out = []
    for x in items:
        if x not in out:
            out.append(x)
    return out


def score(checks: list) -> int:
    s = 100 - sum(PENALTY.get(c["st"], 0) for c in checks)
    return max(0, min(100, s))


def evaluate(facts: dict, prev: dict = None) -> dict:
    """Факти -> {ts, admin, score, checks: [...]}, від найгіршого. prev — попередній результат: картки, яких цей
    збір не торкався (повторна перевірка лише виправленого), беремо з нього."""
    only = set(facts.get("only") or CHECKS)
    old = {c["id"]: c for c in (prev or {}).get("checks") or []}
    checks = []
    for cid in CHECKS:
        if cid in only:
            try:
                c = CHECK_FN[cid](facts)
            except Exception as e:  # дивні дані однієї перевірки не мають ламати решту
                c = _card(cid, UNKNOWN, "hc.err", p=dict(err=f"{type(e).__name__}: {e}"[:120]))
            checks.append(c)
        elif cid in old:
            checks.append(old[cid])
    checks.sort(key=lambda c: (ORDER.get(c["st"], 9), CHECKS.index(c["id"]) if c["id"] in CHECKS else 99))
    out = dict(ts=facts.get("ts") or _now(), admin=facts.get("admin", True), score=score(checks), checks=checks,
               facts=_keep(facts, prev))
    if isinstance(facts.get("crash"), dict):
        out["crash"] = facts["crash"]  # той самий розбір покаже й картка «Чому впав комп?» (не зберігається тут)
    return out


def _keep(facts: dict, prev: dict) -> dict:
    """Факти, потрібні виправленням (профілі брандмауера, стан UAC) — без журналу подій і списку оновлень."""
    ps = facts.get("ps") or ((prev or {}).get("facts") or {}).get("ps") or {}
    return dict(ps={k: ps.get(k) for k in ("fw", "uac", "smb1srv", "smb1cli", "rdp", "autologon", "autorun",
                                            "timesvc", "mp") if k in ps})


def run_check(hw: dict, only=None, prev: dict = None, log=lambda *_: None) -> dict:
    return evaluate(collect(hw, only, log), prev)


def counts(res: dict) -> dict:
    out = {BAD: 0, WARN: 0, UNKNOWN: 0, INFO: 0, OK: 0}
    for c in res.get("checks") or []:
        out[c["st"]] = out.get(c["st"], 0) + 1
    return out


def safe_fixes(res: dict) -> list:
    """Безпечні виправлення з карток із проблемою — для плану «Виправити все безпечне»."""
    out = []
    for c in res.get("checks") or []:
        if c["st"] in (WARN, BAD):
            for fid in c.get("fixes") or []:
                if fid in FIXES and FIXES[fid]["safe"] and fid not in out:
                    out.append(fid)
    return out


# ───────────────────────── виправлення (дозволений список) ─────────────────────────
def psc(code: str) -> str:
    """Команда PowerShell для кроку C(...) і запису відкату (без подвійних лапок усередині code)."""
    return f'powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "{code}"'


SYS_POL = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
WINLOGON = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
RDP_TCP = r"HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp"
EXPL_POL = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\Explorer"
AUTOPLAY = r"HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers"

# safe — може бути в плані «Виправити все безпечне»; kind: act — дія без зміни налаштувань (відкочувати нічого),
# tweak — зміна налаштувань через журнал відкату; check — яку картку перевіряти знову; reboot — діє після перезавантаження
FIXES = {
    "def_sig": dict(safe=True, kind="act", check="defender", cmd="Update-MpSignature", ps="Update-MpSignature",
                    timeout=900),
    # не в плані «усе безпечне»: 5–15 хвилин навантажує диск і процесор — запускають, коли ПК не потрібен для гри
    "def_scan": dict(safe=False, kind="act", check="defender", cmd="Start-MpScan -ScanType QuickScan",
                     ps="Start-MpScan -ScanType QuickScan", timeout=3600),
    # без запису відкату: «повернути як було» тут означало б вимкнути антивірус, а такої команди OptimaX не має
    "def_rtp": dict(safe=True, kind="act", check="defender", cmd="Set-MpPreference -DisableRealtimeMonitoring $false",
                    ps="Set-MpPreference -DisableRealtimeMonitoring $false", timeout=60),
    "time_sync": dict(safe=True, kind="act", check="time", cmd="net start w32time; w32tm /resync /force"),
    "dev_scan": dict(safe=True, kind="act", check="devices", cmd="pnputil /scan-devices"),
    "audio_restart": dict(safe=True, kind="act", check="audio",
                          cmd="net stop Audiosrv /y; net stop AudioEndpointBuilder /y; net start AudioEndpointBuilder; "
                              "net start Audiosrv"),
    "wu_reset": dict(safe=False, kind="act", check="wu",
                     cmd="net stop wuauserv bits cryptsvc msiserver; ren SoftwareDistribution, catroot2; net start …"),
    "time_svc": dict(safe=False, kind="tweak", check="time",
                     cmd="sc config W32Time start= demand; net start w32time; w32tm /resync /force"),
    "fw_on": dict(safe=False, kind="tweak", check="firewall", cmd="netsh advfirewall set <profile> state on"),
    "uac_on": dict(safe=False, kind="tweak", check="uac", reboot=True,
                   cmd=r"reg add HKLM\…\Policies\System /v EnableLUA /d 1; ConsentPromptBehaviorAdmin = 5"),
    "smb1_off": dict(safe=False, kind="tweak", check="smb1", reboot=True,
                     cmd="Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart"),
    "rdp_nla": dict(safe=False, kind="tweak", check="rdp", cmd=r"reg add HKLM\…\WinStations\RDP-Tcp /v UserAuthentication /d 1"),
    "autologon_off": dict(safe=False, kind="tweak", check="autologon",
                          cmd=r"reg add HKLM\…\Winlogon /v AutoAdminLogon /d 0; reg delete … /v DefaultPassword"),
    "autorun_off": dict(safe=False, kind="tweak", check="autorun",
                        cmd=r"reg add HKLM\…\Policies\Explorer /v NoDriveTypeAutoRun /d 255; DisableAutoplay = 1"),
}


def fix_command(fid: str, res: dict = None) -> str:
    if fid == "fw_on":
        off = fw_off(((res or {}).get("facts") or {}).get("ps") or {}) or list(FW_PROFILES)
        return "; ".join(f"netsh advfirewall set {FW_PROFILES[p]} state on" for p in off)
    return FIXES[fid]["cmd"]


def fix_tweak(fid: str, res: dict = None):
    """Зміна налаштувань як запис журналу відкату (E.Tweak з custom=True: її немає в каталогах і «сторожі», але
    сторінка «Резервні копії» й OptimaX-Rescue.cmd повертають її, як і будь-яку іншу)."""
    ps = ((res or {}).get("facts") or {}).get("ps") or {}
    R, C, S = E.R, E.C, E.S
    if fid == "time_svc":
        ops = [S("W32Time", "demand"), C("net start w32time", None, 30), C("w32tm /resync /force", None, 60)]
    elif fid == "fw_on":
        off = fw_off(ps) or list(FW_PROFILES)
        ops = [C(f"netsh advfirewall set {FW_PROFILES[p]} state on", f"netsh advfirewall set {FW_PROFILES[p]} state off")
               for p in off]
    elif fid == "uac_on":
        ops = [R(SYS_POL, "EnableLUA", 1)]
        if (ps.get("uac") or {}).get("cpa") == 0:
            ops.append(R(SYS_POL, "ConsentPromptBehaviorAdmin", 5))
    elif fid == "smb1_off":
        ops = [C(psc("Disable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -NoRestart | Out-Null"),
                 psc("Enable-WindowsOptionalFeature -Online -FeatureName SMB1Protocol -All -NoRestart | Out-Null"),
                 900)]
    elif fid == "rdp_nla":
        ops = [R(RDP_TCP, "UserAuthentication", 1)]
    elif fid == "autologon_off":
        # пароль автовходу не читаємо й не зберігаємо в журналі (він там лежав би відкритим текстом) — лише
        # видаляємо; відкат повертає AutoAdminLogon, але пароль доведеться ввести знову (netplwiz)
        ops = [R(WINLOGON, "AutoAdminLogon", "0", "sz"),
               C(f'reg delete "{WINLOGON}" /v DefaultPassword /f', None, 20)]
    elif fid == "autorun_off":
        ops = [R(EXPL_POL, "NoDriveTypeAutoRun", 255), R(AUTOPLAY, "DisableAutoplay", 1)]
    else:
        return None
    fx = FIXES[fid]
    return E.Tweak(f"hc_{fid}", "system", ops, reboot=bool(fx.get("reboot")), custom=True,
                   _title=tr(f"hc.fix.{fid}"), _desc=tr(f"hc.fixd.{fid}"),
                   reversible=fid != "autologon_off")


def _act(fid: str, log) -> bool:
    fx = FIXES[fid]
    if not E.IS_WIN:
        log(f"  [dry-run] {fx['cmd']}")
        DEMO_FIXED.add(fid)
        return True
    if E.DRY_RUN:
        log(f"  [dry-run] {fx['cmd']}")
        return True
    if fid in ("def_sig", "def_scan", "def_rtp"):
        rc, out = E.ps(fx["ps"], fx["timeout"], log)
        if rc != 0:
            log(f"  ⚠ {E.first_line(out, 90) or rc}")
        return rc == 0
    if fid == "time_sync":
        E.run("net start w32time", 30, log)  # 2 — служба вже працює: не помилка
        rc, out = E.run("w32tm /resync /force", 60, log)
        if rc != 0:
            log(f"  ⚠ {E.first_line(out, 90) or rc}")
        return rc == 0
    if fid == "dev_scan":
        rc, out = E.run("pnputil /scan-devices", 120, log)
        if rc != 0:
            log(f"  ⚠ {E.first_line(out, 90) or rc}")
        return rc == 0
    if fid == "audio_restart":
        E.a_fix_audio(E.Ctx(log))
        return True
    if fid == "wu_reset":
        E.a_reset_wu(E.Ctx(log))
        return True
    return False


def run_fix(fid: str, res: dict, log, restore_point: bool = False) -> dict:
    """Одне виправлення. -> {ok, reboot, fid}."""
    fx = FIXES.get(fid)
    if not fx:
        return dict(fid=fid, ok=False, error="unknown")
    log(f"\n[►] {tr(f'hc.fix.{fid}')}")
    if fx["kind"] == "act":
        if restore_point:
            E.create_restore_point(log)
        try:
            ok = _act(fid, log)
        except Exception as e:
            log(tr("e.err", err=f"{type(e).__name__}: {e}"))
            ok = False
        return dict(fid=fid, ok=ok, reboot=False)
    t = fix_tweak(fid, res)
    r = E.apply_tweaks([t], log, header=False, restore_point=restore_point)
    ok = bool(r.get("ok") or r.get("already")) and not r.get("fail") and not r.get("partial") and not r.get("error")
    if ok and not E.IS_WIN:
        DEMO_FIXED.add(fid)
    return dict(fid=fid, ok=ok, reboot=bool(fx.get("reboot")) and ok, partial=bool(r.get("partial")))


def resolved(fid: str, res: dict) -> bool:
    """Чи зникла саме та проблема, яку виправляло fid (а не вся картка: після оновлення сигнатур Defender може
    й далі просити сканування)."""
    c = next((x for x in res.get("checks") or [] if x["id"] == FIXES[fid]["check"]), None)
    if c is None:
        return False
    if c["st"] in (OK, INFO):
        return fid != "autorun_off" or c["head"][0] == "hc.ar.ok"
    return fid not in (c.get("fixes") or [])


def run_plan(fids, hw: dict, res: dict, log, progress=None, restore_point: bool = False) -> dict:
    """«Виправити все безпечне» (або кілька вибраних): по черзі, невдале не зупиняє наступне; потім повторна
    перевірка лише зачеплених карток. -> {results: [{fid, outcome}], health: новий результат, ok, fail}."""
    fids = [f for f in fids if f in FIXES]
    total = len(fids) + 1
    done = []
    rp = restore_point
    for i, fid in enumerate(fids):
        if E.CANCEL.is_set():
            log(tr("e.stopped"))
            break
        if progress:
            progress(i, total, tr(f"hc.fix.{fid}"))
        use_rp = rp and FIXES[fid]["kind"] == "tweak"  # точка відновлення — перед першою зміною налаштувань
        rp = rp and not use_rp
        done.append(run_fix(fid, res, log, restore_point=use_rp))
    if progress:
        progress(len(fids), total, tr("hc.recheck"))
    log("\n" + tr("hc.recheck"))
    only = sorted({FIXES[d["fid"]]["check"] for d in done})
    new = run_check(hw, only, res, log) if only else res
    out = []
    for d in done:
        if not d["ok"]:
            o = "failed"
        elif d.get("reboot"):
            o = "reboot"
        elif d["fid"] == "wu_reset":
            o = "done"  # що компоненти оновлення полагоджено, покаже лише наступна спроба оновитися
        elif resolved(d["fid"], new):
            o = "fixed"
        else:
            o = "still"
        out.append(dict(fid=d["fid"], outcome=o))
        log(f"  {tr('hc.out.' + o)} — {tr('hc.fix.' + d['fid'])}")
    if progress:
        progress(total, total, tr("e.finished"))
    fail = sum(1 for x in out if x["outcome"] == "failed")
    return dict(results=out, health=new, ok=len(out) - fail, fail=fail,
                reboot=any(x["outcome"] == "reboot" for x in out))


def report_lines(res: dict) -> list:
    """Для звіту: (назва перевірки, стан і суть) — без імен ПК, користувача й мереж."""
    out = []
    for c in (res or {}).get("checks") or []:
        k, p = c["head"]
        out.append((tr(f"hc.c.{c['id']}"), f"{tr('hc.st.' + c['st'])} — {tr(k, **p)}"))
    return out
