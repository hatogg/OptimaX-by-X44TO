"""
OptimaX — функції поверх ядра: налаштування програми, режим гри, список ігор, фоновий чистильник
пам'яті, автозавантаження, автозапуск із треєм, експорт/імпорт, майстер із питаннями.
"""
from __future__ import annotations

import json
import ntpath
import os
import subprocess
import sys
import time

import engine as E
import hardware as H
from i18n import tr, CONFIG_PATH

# ───────────────────────── налаштування програми ─────────────────────────
DEFAULTS = {
    "language": None,
    "close_to_tray": True,
    "tray_hint_shown": False,
    "games": [],  # [{path, prio, dgpu, fso, boost, cores}]
    "booster": {"services": True, "kill": True, "purge": True, "power": True, "timer": True, "auto": True,
                "dnd": True, "balance": True},
    "booster_state": None,
    "cleaner": {"enabled": False, "standby_mb": 1024, "free_mb": 1024},
    "timer_hold": False,
    "snapshot": None,  # заміри «до»
    "first_run": True,
    "guard": {"enabled": True},
    "guard_state": None,  # {ts, os, reverted}
    "trial": None,  # {ids, ts, boot}
    "schedule": {"enabled": False, "day": 6, "hour": 12},
    "maint_last": None,
    "hotkeys": True,
    "refresh_power": {"enabled": False, "battery_hz": 60},
    "charge_limit": None,  # {method, pct}
    "fps_tests": {},  # {exe: {before, after}}
    "diag_last": None,
    "net": {},
    "updates": {"auto": True, "last_check": 0, "skip": None},
    "bench": [],  # результати тестів відеокарти
    "adblock": {"mode": "off", "light": None},  # off | filter | light
    "safety": None,  # останній пакет змін для перевірки стабільності {ts, ids, kind, boot, checked}
    "smart": None,  # незавершена розумна оптимізація (продовжується після перезавантаження)
    "smart_last": None,  # підсумок останньої розумної оптимізації
    "smart_pref": {"provider": "gpu", "game": None},
}


class Config:
    def __init__(self, path: str = CONFIG_PATH):
        self.path = path
        self.data = json.loads(json.dumps(DEFAULTS))
        try:
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(self.data.get(k), dict):
                    self.data[k].update(v)
                else:
                    self.data[k] = v
        except Exception:
            pass

    def __getitem__(self, k):
        return self.data.get(k)

    def __setitem__(self, k, v):
        self.data[k] = v
        self.save()

    def save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception:
            pass


CFG = Config()

# ───────────────────────── режим гри ─────────────────────────
BOOST_SERVICES = ["WSearch", "SysMain", "DiagTrack", "WerSvc", "BITS", "DoSvc", "wuauserv", "Spooler", "MapsBroker"]
BOOST_KILL = ["OneDrive.exe", "MicrosoftEdgeUpdate.exe", "Widgets.exe", "WidgetService.exe",
              "PhoneExperienceHost.exe", "YourPhone.exe", "CompatTelRunner.exe", "SkypeApp.exe"]
ONEDRIVE_EXE = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "OneDrive", "OneDrive.exe")


def service_running(name: str) -> bool:
    if not E.IS_WIN:
        return name in ("WSearch", "SysMain", "DiagTrack", "BITS", "Spooler")
    rc, out = E.run(f"sc query {name}", 8, ro=True)
    return rc == 0 and "RUNNING" in out.upper()


class GameBooster:
    """Тимчасовий режим гри: усе, що змінено, повертається після вимкнення (навіть після збою)."""

    def __init__(self, cfg: Config = CFG):
        self.cfg = cfg

    @property
    def active(self) -> bool:
        return bool(self.cfg["booster_state"])

    def start(self, log) -> dict:
        if self.active:
            return {"ok": True}
        opt = self.cfg["booster"]
        state = {"ts": int(time.time()), "services": [], "onedrive": False, "plan": None, "timer": False,
                 "dnd": None}
        self.cfg["booster_state"] = state  # одразу зберігаємо, щоб відновити після аварійного закриття
        log(tr("g.boost_on"))
        if opt.get("power"):
            old = E.active_scheme()
            new, _ = E.ensure_ultimate(log) if E.IS_WIN else (E.HIGH_PERF, False)
            if new != old:
                E.run(f"powercfg -setactive {new}", 15, log)
                state["plan"] = old
                log(tr("g.plan"))
        if opt.get("services"):
            for s in BOOST_SERVICES:
                if service_running(s):
                    E.run(f"net stop {s} /y", 30, log)
                    state["services"].append(s)
            log(tr("g.services", n=len(state["services"])))
        if opt.get("kill"):
            names = {n.lower() for _, n in E.processes()}
            state["onedrive"] = "onedrive.exe" in names
            n = 0
            for p in BOOST_KILL:
                if p.lower() in names:
                    E.run(f"taskkill /f /im {p}", 8, log)
                    n += 1
            log(tr("g.killed", n=n))
        if opt.get("purge"):
            E.purge_standby()
            log(tr("g.purged"))
        if opt.get("timer"):
            state["timer"] = E.set_timer_resolution(True)
            log(tr("g.timer"))
        if opt.get("dnd"):
            cur = E.reg_get(NOTIF_KEY, NOTIF_VAL)
            state["dnd"] = cur[1] if cur else -1
            _set_toasts(0)
            log(tr("g.dnd"))
        self.cfg["booster_state"] = state
        return {"ok": True}

    def stop(self, log) -> dict:
        state = self.cfg["booster_state"]
        if not state:
            return {"ok": True}
        log(tr("g.boost_off"))
        for s in state.get("services", []):
            E.run(f"net start {s}", 30, log)
        if state.get("plan"):
            E.run(f"powercfg -setactive {state['plan']}", 15, log)
        if state.get("onedrive") and os.path.exists(ONEDRIVE_EXE) and not E.DRY_RUN:
            try:
                subprocess.Popen([ONEDRIVE_EXE, "/background"], creationflags=E.CREATE_NO_WINDOW)
            except OSError:
                pass
        if state.get("timer") and not CFG["timer_hold"]:
            E.set_timer_resolution(False)
        if state.get("dnd") is not None:
            _set_toasts(None if state["dnd"] == -1 else state["dnd"])
        self.cfg["booster_state"] = None
        log(tr("g.restored"))
        return {"ok": True}


NOTIF_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Notifications\Settings"
NOTIF_VAL = "NOC_GLOBAL_SETTING_TOASTS_ENABLED"


def _set_toasts(value) -> None:
    """Вмикає/вимикає спливаючі сповіщення Windows. None — повернути стандартну поведінку."""
    if E.DRY_RUN or not E.IS_WIN:
        return
    try:
        if value is None:
            E.reg_del_value(NOTIF_KEY, NOTIF_VAL)
        else:
            E.reg_set(NOTIF_KEY, NOTIF_VAL, int(value), "dword")
        import ctypes
        res = ctypes.c_ulong(0)
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Policy", 2, 2000, ctypes.byref(res))
    except OSError:
        pass


BOOSTER = GameBooster()

# ───────────────────────── ігри ─────────────────────────
IFEO = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
LAYERS = r"HKCU\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
GAME_OPTS = ("prio", "dgpu", "fso")


def game_name(path: str) -> str:
    base = ntpath.splitext(ntpath.basename(path))[0]
    if base.islower() and len(base) <= 4:
        return base.upper()
    return base[:1].upper() + base[1:]


def _fso_value(path: str) -> str:
    cur = E.reg_get(LAYERS, path)
    tokens = [x for x in (str(cur[1]).split() if cur else []) if x != "~"]
    if "DISABLEDXMAXIMIZEDWINDOWEDMODE" not in tokens:
        tokens.append("DISABLEDXMAXIMIZEDWINDOWEDMODE")
    return "~ " + " ".join(tokens)


def game_tweak(path: str, opt: str) -> E.Tweak:
    exe = ntpath.basename(path)
    if opt == "prio":
        ops = [E.R(f"{IFEO}\\{exe}\\PerfOptions", "CpuPriorityClass", 3), E.R(f"{IFEO}\\{exe}\\PerfOptions", "IoPriority", 3)]
    elif opt == "dgpu":
        ops = [E.R(E.DX_PREF, path, "GpuPreference=2;", "sz")]
    else:
        ops = [E.D(lambda ctx, p=path: [E.R(LAYERS, p, _fso_value(p), "sz")])]
    t = E.Tweak(f"game:{path.lower()}:{opt}", "game", ops)
    t._title = f"{game_name(path)}: {tr('games.opt.' + opt)}"
    return t


def set_game_option(path: str, opt: str, on: bool, log) -> dict:
    t = game_tweak(path, opt)
    if on:
        return E.apply_tweaks([t], log, header=False)
    E.undo_ids([t.id], log)
    return {"ok": 1}


def add_game(path: str) -> bool:
    games = CFG["games"] or []
    if any(g["path"].lower() == path.lower() for g in games):
        return False
    games.append({"path": path, "prio": False, "dgpu": False, "fso": False, "boost": True, "cores": False})
    CFG["games"] = games
    return True


def remove_game(path: str, log) -> dict:
    ids = [f"game:{path.lower()}:{o}" for o in GAME_OPTS if E.JOURNAL.has(f"game:{path.lower()}:{o}")]
    if ids:
        E.undo_ids(ids, log)
    CFG["games"] = [g for g in CFG["games"] if g["path"].lower() != path.lower()]
    return {"ok": 1}


def update_game(path: str, **kw) -> None:
    games = CFG["games"]
    for g in games:
        if g["path"].lower() == path.lower():
            g.update(kw)
    CFG["games"] = games


SYS_DIRS = tuple(p.lower() for p in (os.environ.get("SystemRoot", r"C:\Windows"),
                                     os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WindowsApps"))
                 if p)
SKIP_EXE = {"explorer.exe", "svchost.exe", "python.exe", "pythonw.exe", "optimax.exe", "steam.exe",
            "steamwebhelper.exe", "epicgameslauncher.exe", "discord.exe", "chrome.exe", "msedge.exe", "firefox.exe",
            "opera.exe", "browser.exe", "telegram.exe", "spotify.exe", "code.exe", "nvcontainer.exe",
            "nvidia share.exe", "radeonsoftware.exe", "msiafterburner.exe", "rtsshooksloader64.exe"}


def running_apps() -> list:
    """Запущені зараз програми, схожі на ігри: [(назва, шлях)]."""
    if not E.IS_WIN:
        return [("Cs2", r"C:\Games\Counter-Strike Global Offensive\game\bin\win64\cs2.exe"),
                ("Valorant", r"C:\Riot Games\VALORANT\live\VALORANT.exe")]
    seen, res = set(), []
    me = os.path.abspath(sys.executable).lower()
    for pid, name in E.processes():
        low = name.lower()
        if low in SKIP_EXE or low in seen or not low.endswith(".exe"):
            continue
        path = E.process_path(pid)
        if not path or path.lower() == me or path.lower().startswith(SYS_DIRS):
            continue
        seen.add(low)
        res.append((game_name(path), path))
    return sorted(res)


def running_game_names() -> set:
    return {n.lower() for _, n in E.processes()}


# ───────────────────────── автозавантаження ─────────────────────────
APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
RUN_SOURCES = [
    ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Run", "st.src.user"),
    ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "Run", "st.src.all"),
    ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Run32", "st.src.all"),
]


def _approved_state(hive: str, sub: str, name: str) -> bool:
    v = E.reg_get(f"{hive}\\{APPROVED}\\{sub}", name)
    if not v or not isinstance(v[1], (bytes, bytearray)) or not v[1]:
        return True
    return v[1][0] in (0x02, 0x06)


def _exe_from_cmd(cmd: str) -> str:
    cmd = os.path.expandvars(cmd.strip())
    if cmd.startswith('"'):
        return cmd[1:].split('"', 1)[0]
    low = cmd.lower()
    i = low.find(".exe")
    return cmd[:i + 4] if i > 0 else cmd.split(" ")[0]


DEMO_STARTUP = [
    dict(id="reg|HKCU|Run|Discord", name="Discord", cmd=r"C:\Users\User\AppData\Local\Discord\Update.exe --processStart Discord.exe",
         src="st.src.user", kind="reg", enabled=True),
    dict(id="reg|HKCU|Run|Steam", name="Steam", cmd=r'"C:\Program Files (x86)\Steam\steam.exe" -silent',
         src="st.src.user", kind="reg", enabled=True),
    dict(id="reg|HKLM|Run|SecurityHealth", name="Windows Security notification icon",
         cmd=r"%windir%\system32\SecurityHealthSystray.exe", src="st.src.all", kind="reg", enabled=True),
    dict(id="folder|HKCU|StartupFolder|Spotify.lnk", name="Spotify", cmd="Spotify.lnk", src="st.src.folder",
         kind="folder", enabled=False),
    dict(id=r"task|\GoogleUpdateTaskMachineUA", name="GoogleUpdateTaskMachineUA",
         cmd=r"C:\Program Files (x86)\Google\Update\GoogleUpdate.exe /ua", src="st.src.task", kind="task", enabled=True),
]
_demo_state: dict = {}


def startup_items() -> list:
    if not E.IS_WIN:
        return [dict(d, enabled=_demo_state.get(d["id"], d["enabled"])) for d in DEMO_STARTUP]
    items = []
    for hive, path, sub, src in RUN_SOURCES:
        for name, val, _t in E.reg_values(f"{hive}\\{path}"):
            if not name:
                continue
            items.append(dict(id=f"reg|{hive}|{sub}|{name}", name=name, cmd=str(val), src=src, kind="reg",
                              enabled=_approved_state(hive, sub, name), file=_exe_from_cmd(str(val))))
    folders = [("HKCU", os.path.join(E.APPDATA, r"Microsoft\Windows\Start Menu\Programs\Startup")),
               ("HKLM", os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"),
                                     r"Microsoft\Windows\Start Menu\Programs\StartUp"))]
    for hive, folder in folders:
        try:
            files = [f for f in os.listdir(folder) if f.lower() != "desktop.ini"]
        except OSError:
            files = []
        for f in files:
            items.append(dict(id=f"folder|{hive}|StartupFolder|{f}", name=os.path.splitext(f)[0], cmd=f,
                              src="st.src.folder", kind="folder", enabled=_approved_state(hive, "StartupFolder", f),
                              file=os.path.join(folder, f)))
    data = E.ps_json(
        "Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\\Microsoft\\*' -and $_.TaskName -ne 'OptimaX' -and "
        "($_.Triggers | Where-Object { $_.CimClass.CimClassName -eq 'MSFT_TaskLogonTrigger' }) } | "
        "Select-Object @{n='p';e={$_.TaskPath + $_.TaskName}}, @{n='s';e={[string]$_.State}}, "
        "@{n='x';e={($_.Actions | Select-Object -First 1).Execute}} | ConvertTo-Json -Compress", 60)
    for t in E.as_list(data):
        if not isinstance(t, dict) or not t.get("p"):
            continue
        items.append(dict(id=f"task|{t['p']}", name=t["p"].rsplit("\\", 1)[-1], cmd=str(t.get("x") or ""),
                          src="st.src.task", kind="task", enabled=t.get("s") != "Disabled",
                          file=os.path.expandvars(str(t.get("x") or "").strip('"'))))
    return sorted(items, key=lambda i: (not i["enabled"], i["name"].lower()))


def set_startup(item: dict, on: bool, log) -> dict:
    if not E.IS_WIN or E.DRY_RUN:
        _demo_state[item["id"]] = on
        log(f"  [dry-run] startup {item['name']} → {'on' if on else 'off'}")
        return {"ok": True}
    kind = item["kind"]
    if kind == "task":
        path = item["id"].split("|", 1)[1]
        rc, out = E.run(["schtasks", "/Change", "/TN", path, "/Enable" if on else "/Disable"], 20, log)
        return {"ok": rc == 0, "error": None if rc == 0 else E.first_line(out)}
    _, hive, sub, name = item["id"].split("|", 3)
    stamp = int((time.time() + 11644473600) * 10**7).to_bytes(8, "little")
    data = bytes([2, 0, 0, 0]) + bytes(8) if on else bytes([3, 0, 0, 0]) + stamp
    try:
        E.reg_set(f"{hive}\\{APPROVED}\\{sub}", name, data, "bin")
        return {"ok": True}
    except OSError as e:
        return {"ok": False, "error": str(e)}


# ───────────────────────── автозапуск OptimaX і трей ─────────────────────────
TASK_NAME = "OptimaX"


def _self_command() -> list:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return [pyw if os.path.exists(pyw) else exe, os.path.abspath(sys.argv[0])]


def autostart_enabled() -> bool:
    if not E.IS_WIN:
        return bool(CFG["demo_autostart"])
    rc, _ = E.run(["schtasks", "/Query", "/TN", TASK_NAME], 10, ro=True)
    return rc == 0


def set_autostart(on: bool, log=lambda *_: None) -> bool:
    if not E.IS_WIN or E.DRY_RUN:
        CFG["demo_autostart"] = on
        return True
    if on:
        tr_cmd = subprocess.list2cmdline(_self_command() + ["--tray"])
        rc, out = E.run(["schtasks", "/Create", "/TN", TASK_NAME, "/TR", tr_cmd, "/SC", "ONLOGON", "/RL", "HIGHEST",
                         "/IT", "/DELAY", "0000:20", "/F"], 20, log)
    else:
        rc, out = E.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], 20, log)
    return rc == 0


# ───────────────────────── експорт / імпорт ─────────────────────────
def export_profile(path: str, selected: list, profile: str) -> None:
    data = {"app": E.APP_NAME, "version": E.VERSION, "selected": selected, "profile": profile,
            "games": CFG["games"], "booster": CFG["booster"], "cleaner": CFG["cleaner"],
            "timer_hold": CFG["timer_hold"], "language": CFG["language"], "guard": CFG["guard"],
            "schedule": CFG["schedule"], "hotkeys": CFG["hotkeys"], "refresh_power": CFG["refresh_power"]}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def import_profile(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("app") != E.APP_NAME:
        raise ValueError(tr("set.import_bad"))
    data["selected"] = [i for i in data.get("selected", []) if i in E.BY_ID]
    for k in ("booster", "cleaner", "guard", "refresh_power"):
        if isinstance(data.get(k), dict):
            cur = CFG[k]
            cur.update(data[k])
            CFG[k] = cur
    if isinstance(data.get("games"), list):
        known = {g["path"].lower() for g in CFG["games"]}
        CFG["games"] = CFG["games"] + [g for g in data["games"]
                                       if isinstance(g, dict) and g.get("path") and g["path"].lower() not in known]
    return data


# ───────────────────────── майстер (опитувальник) ─────────────────────────
WIZARD = [
    {"id": "device", "opts": ["gaming", "laptop", "old", "xeon"]},
    {"id": "usage", "opts": ["games", "mixed", "work"]},
    {"id": "goal", "opts": ["latency", "fps", "quiet"], "when": ("usage", ("games", "mixed"))},
    {"id": "av", "opts": ["defender", "other"]},
    {"id": "ms", "opts": ["onedrive", "xbox", "search", "copilot"], "multi": True},
]
DEVICE_PROFILE = {"gaming": "M", "laptop": "T", "old": "O", "xeon": "X"}
LATENCY = ["processor_idle", "timer_resolution", "dynamic_tick", "msi_gpu", "disable_nagle", "network_stack_boost",
           "fso_global", "turbo_aggressive"]
FPS = ["disable_vbs", "msi_gpu", "fso_global", "turbo_aggressive"]
HOT = ["ultimate_power", "processor_idle", "power_throttling", "turbo_aggressive", "core_parking", "min_cpu_state",
       "laptop_ac_max", "pcie_aspm"]
AI_FEATURES = ["ai_copilot", "ai_recall", "ai_click_to_do", "ai_apps", "ai_edge", "search_no_bing"]
GAME_ONLY = ["disable_mouse_accel", "fso_global", "hpet_tsc", "timer_resolution", "dynamic_tick", "msi_gpu"]


def wizard_defaults(hw: dict) -> dict:
    return {"device": hw.get("device", "gaming"), "usage": "mixed", "goal": "fps", "av": "defender", "ms": []}


def build_plan(ans: dict, hw: dict) -> list:
    prof = DEVICE_PROFILE.get(ans.get("device"), "M")
    ids = {t.id for t in E.TWEAKS if prof in t.p}
    usage, goal = ans.get("usage"), ans.get("goal")
    desktop = ans.get("device") in ("gaming", "xeon")
    if usage in ("games", "mixed"):
        if goal == "latency":
            ids |= {i for i in LATENCY if desktop or i not in HOT}
        elif goal == "fps":
            ids |= {i for i in FPS if desktop or i not in HOT}
        elif goal == "quiet":
            ids -= set(HOT)
            ids.add("cool_mode")
    else:
        ids -= set(GAME_ONLY)
    # інший антивірус сам переводить Defender у пасивний режим; вимикати його політикою не можна — якщо той
    # антивірус колись видалять, ПК лишиться без жодного захисту
    ids.discard("disable_defender")
    if ans.get("av") == "other":
        ids.discard("defender_limit")
    else:
        ids.add("defender_limit")
    ms = set(ans.get("ms") or [])
    ids.discard("remove_onedrive")  # видалення OneDrive — лише вручну: файли «лише в хмарі» стають недоступні
    if "xbox" in ms:
        ids.discard("disable_xbox_gamebar")
    if "search" in ms:
        ids.discard("disable_search_index")
    if "copilot" in ms:
        ids -= set(AI_FEATURES)
    order = {t.id: i for i, t in enumerate(E.TWEAKS)}
    plan = []
    for i in sorted(ids, key=lambda x: order.get(x, 999)):
        t = E.BY_ID.get(i)
        if not t or t.group in ("visual",):
            continue
        if E.compat(t, hw)[0] in ("na", "block"):
            continue
        plan.append(i)
    return plan
