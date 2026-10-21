"""
OptimaX — програми та місце на диску: оновлення всіх програм і встановлення популярних через winget,
пошук старих версій драйверів у сховищі драйверів, аналізатор зайнятого місця.
"""
from __future__ import annotations

import heapq
import os
import re
import shutil
import stat
import time

import engine as E
from i18n import tr

# ───────────────────────── winget ─────────────────────────
CATALOG = [
    ("games", [("Valve.Steam", "Steam"), ("EpicGames.EpicGamesLauncher", "Epic Games"), ("GOG.Galaxy", "GOG Galaxy"),
               ("Blizzard.BattleNet", "Battle.net"), ("ElectronicArts.EADesktop", "EA app"),
               ("Ubisoft.Connect", "Ubisoft Connect")]),
    ("chat", [("Discord.Discord", "Discord"), ("Telegram.TelegramDesktop", "Telegram"), ("Zoom.Zoom", "Zoom")]),
    ("browsers", [("Google.Chrome", "Google Chrome"), ("Mozilla.Firefox", "Firefox"), ("Brave.Brave", "Brave"),
                  ("Opera.OperaGX", "Opera GX")]),
    ("tools", [("7zip.7zip", "7-Zip"), ("voidtools.Everything", "Everything"), ("ShareX.ShareX", "ShareX"),
               ("Microsoft.PowerToys", "PowerToys"), ("Notepad++.Notepad++", "Notepad++"), ("VideoLAN.VLC", "VLC"),
               ("OBSProject.OBSStudio", "OBS Studio")]),
    ("hw", [("Guru3D.Afterburner", "MSI Afterburner"), ("REALiX.HWiNFO", "HWiNFO"), ("CPUID.CPU-Z", "CPU-Z"),
            ("TechPowerUp.GPU-Z", "GPU-Z"), ("CrystalDewWorld.CrystalDiskInfo", "CrystalDiskInfo")]),
    ("runtime", [("Microsoft.VCRedist.2015+.x64", "Visual C++ 2015–2022 x64"),
                 ("Microsoft.VCRedist.2015+.x86", "Visual C++ 2015–2022 x86"),
                 ("Microsoft.DotNet.DesktopRuntime.8", ".NET Desktop Runtime 8"),
                 ("Microsoft.DirectX", "DirectX End-User Runtime")]),
]
WG_FLAGS = ["--silent", "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"]
DEMO_UPGRADES = [dict(name="Discord", id="Discord.Discord", version="1.0.9171", available="1.0.9182", source="winget"),
                 dict(name="Google Chrome", id="Google.Chrome", version="129.0.6668.90", available="130.0.6723.70",
                      source="winget"),
                 dict(name="7-Zip 23.01 (x64)", id="7zip.7zip", version="23.01", available="24.08", source="winget"),
                 dict(name="Steam", id="Valve.Steam", version="2.10.91.91", available="Unknown", source="winget")]
DEMO_INSTALLED = {"Valve.Steam", "Discord.Discord", "Google.Chrome", "7zip.7zip", "Microsoft.VCRedist.2015+.x64"}


def winget_path():
    if not E.IS_WIN:
        return "winget"
    p = shutil.which("winget")
    if p:
        return p
    cand = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe")
    return cand if os.path.exists(cand) else None


def _rows(out: str) -> list:
    """Рядки таблиці winget після лінії з дефісів."""
    lines = out.replace("\r", "\n").splitlines()
    for i, ln in enumerate(lines):
        if re.fullmatch(r"\s*-{10,}\s*", ln):
            return [x for x in lines[i + 1:] if x.strip()]
    return []


def parse_upgrades(out: str) -> list:
    res = []
    for ln in _rows(out):
        tok = ln.split()
        if len(tok) < 4 or tok[-1].lower() not in ("winget", "msstore"):
            continue
        src, avail, ver = tok[-1], tok[-2], tok[-3]
        rest = tok[:-3]
        if rest and rest[-1] in ("<", ">"):  # «< 1.2.3» — версія з пробілом
            ver = rest.pop() + " " + ver
        if len(rest) < 2:
            continue
        pkg = rest[-1]
        if "." not in pkg:
            continue
        res.append(dict(name=" ".join(rest[:-1]), id=pkg, version=ver, available=avail, source=src))
    return res


def list_upgrades(log) -> list:
    wg = winget_path()
    if not wg:
        raise RuntimeError(tr("apps.no_winget"))
    if not E.IS_WIN:
        log(tr("apps.found_upd", n=len(DEMO_UPGRADES)))
        return [dict(u) for u in DEMO_UPGRADES]
    rc, out = E.run([wg, "upgrade", "--include-unknown", "--accept-source-agreements"], 180, ro=True, enc="utf-8")
    ups = parse_upgrades(out)
    log(tr("apps.found_upd", n=len(ups)))
    return ups


def installed_ids(ids) -> set:
    if not E.IS_WIN:
        return {i for i in ids if i in DEMO_INSTALLED}
    wg = winget_path()
    if not wg:
        return set()
    _, out = E.run([wg, "list", "--accept-source-agreements"], 180, ro=True, enc="utf-8")
    low = out.lower()
    return {i for i in ids if i.lower() in low}


def _winget_job(args_list, log, progress, verb: str) -> dict:
    wg = winget_path()
    if not wg:
        raise RuntimeError(tr("apps.no_winget"))
    ok = fail = 0
    for n, (pkg, name) in enumerate(args_list):
        if E.CANCEL.is_set():
            break
        if progress:
            progress(n, len(args_list), name)
        log(f"\n[►] {name}")
        cmd = [wg, verb, "-e", "--id", pkg] + WG_FLAGS
        rc, out = E.run(cmd, 1800, log, enc="utf-8")
        lines = [x.strip() for x in out.replace("\r", "\n").splitlines()
                 if x.strip() and not re.fullmatch(r"[\s█▒░\-\\|/.0-9%KMGBkmgb]+", x.strip())]
        for x in lines[-3:]:
            log(f"  {x[:110]}")
        if rc in (0, -1978335189):  # -1978335189 = вже найновіша версія
            ok += 1
            log(tr("e.done"))
        else:
            fail += 1
            log(tr("apps.fail_code", rc=rc))
    if progress:
        progress(len(args_list), len(args_list), tr("e.finished"))
    log("\n" + tr("apps.summary", ok=ok, fail=fail))
    return {"ok": ok, "fail": fail}


def install(items, log, progress=None) -> dict:
    return _winget_job(items, log, progress, "install")


def upgrade(items, log, progress=None) -> dict:
    return _winget_job(items, log, progress, "upgrade")


# ───────────────────────── старі драйвери ─────────────────────────
DRIVERS_SCRIPT = r"""
$use=@{}; Get-CimInstance Win32_PnPSignedDriver -ErrorAction SilentlyContinue | ForEach-Object { if ($_.InfName) { $use[$_.InfName.ToLower()]=1 } }
Get-WindowsDriver -Online -ErrorAction Stop | ForEach-Object {
  @{inf=$_.Driver; orig=$_.OriginalFileName; prov=$_.ProviderName; cls=$_.ClassName; ver=$_.Version;
    date=$(if($_.Date){$_.Date.ToString('yyyy-MM-dd')}); used=[bool]$use[$_.Driver.ToLower()]} } | ConvertTo-Json -Compress
"""
DEMO_DRIVERS = [
    ("oem41.inf", "nv_dispi.inf", "NVIDIA", "Display", "32.0.15.5612", "2024-06-24", False, 1180),
    ("oem57.inf", "nv_dispi.inf", "NVIDIA", "Display", "32.0.15.6094", "2024-08-14", False, 1215),
    ("oem63.inf", "nv_dispi.inf", "NVIDIA", "Display", "32.0.15.6603", "2024-11-25", True, 1240),
    ("oem12.inf", "hdxrt.inf", "Realtek Semiconductor Corp.", "MEDIA", "6.0.9235.1", "2021-09-03", False, 96),
    ("oem33.inf", "hdxrt.inf", "Realtek Semiconductor Corp.", "MEDIA", "6.0.9549.1", "2023-07-11", True, 98),
    ("oem20.inf", "netrtwlane.inf", "Realtek", "Net", "2024.0.10.204", "2023-12-01", True, 14),
]


def _ver_key(v: str):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", v or "0"))


def _dir_size(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def old_drivers(log) -> list:
    """Старі версії тих самих драйверів (не використовуються жодним пристроєм). Найновішу не чіпаємо."""
    if not E.IS_WIN:
        rows = [dict(inf=a, orig=b, prov=c, cls=d, ver=e, date=f, used=g, size_mb=h) for a, b, c, d, e, f, g, h in
                DEMO_DRIVERS]
    else:
        data = E.ps_json(DRIVERS_SCRIPT, 240) or []
        rows = []
        for d in E.as_list(data):
            if not isinstance(d, dict) or not d.get("inf"):
                continue
            orig = str(d.get("orig") or "")
            size = _dir_size(os.path.dirname(orig)) if orig and os.path.isdir(os.path.dirname(orig)) else 0
            rows.append(dict(inf=d["inf"], orig=os.path.basename(orig).lower(), prov=str(d.get("prov") or ""),
                             cls=str(d.get("cls") or ""), ver=str(d.get("ver") or ""), date=str(d.get("date") or ""),
                             used=bool(d.get("used")), size_mb=round(size / 2**20)))
    groups = {}
    for r in rows:
        groups.setdefault((r["orig"], r["prov"].lower(), r["cls"].lower()), []).append(r)
    old = []
    for items in groups.values():
        if len(items) < 2:
            continue
        items.sort(key=lambda r: (_ver_key(r["ver"]), r["date"]))
        newest = items[-1]
        old += [r for r in items[:-1] if not r["used"] and r is not newest]
    old.sort(key=lambda r: -r["size_mb"])
    log(tr("drv.found", n=len(old), mb=sum(r["size_mb"] for r in old)))
    return old


def delete_drivers(items, log, progress=None) -> dict:
    ok = 0
    for i, r in enumerate(items):
        if E.CANCEL.is_set():
            break
        if progress:
            progress(i, len(items), f"{r['prov']} {r['ver']}")
        rc, out = E.run(["pnputil", "/delete-driver", r["inf"]], 60, log)
        if rc == 0:
            ok += 1
            log(tr("drv.deleted", inf=r["inf"], prov=r["prov"], ver=r["ver"]))
        else:
            log(tr("drv.kept", inf=r["inf"]))
    if progress:
        progress(len(items), len(items), tr("e.finished"))
    log(tr("drv.summary", n=ok))
    return {"ok": ok}


# ───────────────────────── аналізатор місця ─────────────────────────
REPARSE = 0x400


class DiskScan:
    """Розміри папок (до глибини MAX_DEPTH) і найбільші файли. Посилання та точки з'єднання не обходимо."""
    MAX_DEPTH = 7

    def __init__(self, root: str):
        self.root = os.path.normpath(root)
        self.sizes, self.children, self.own = {}, {}, {}
        self.files = []
        self.nfiles = self.ndirs = self.errors = 0

    def run(self, progress=None) -> "DiskScan":
        if not E.IS_WIN:
            return self._demo()
        stack = [(self.root, 0, None)]
        order = []
        t_last = 0.0
        while stack:
            if E.CANCEL.is_set():
                break
            path, depth, parent = stack.pop()
            order.append((path, depth, parent))
            kids, own = [], 0
            try:
                with os.scandir(path) as it:
                    for e in it:
                        try:
                            st = e.stat(follow_symlinks=False)
                            if getattr(st, "st_file_attributes", 0) & REPARSE:
                                continue
                            if stat.S_ISDIR(st.st_mode):
                                kids.append(e.path)
                                stack.append((e.path, depth + 1, path))
                                self.ndirs += 1
                            else:
                                own += st.st_size
                                self.nfiles += 1
                                if len(self.files) < 30:
                                    heapq.heappush(self.files, (st.st_size, e.path))
                                elif st.st_size > self.files[0][0]:
                                    heapq.heapreplace(self.files, (st.st_size, e.path))
                        except OSError:
                            self.errors += 1
            except OSError:
                self.errors += 1
            if own:
                self.own[path] = own
            if depth < self.MAX_DEPTH:
                self.children[path] = kids
            now = time.perf_counter()
            if progress and now - t_last > 0.25:
                t_last = now
                progress(0, 0, tr("disk.scanning", n=self.nfiles, path=path[-60:]))
        # згортаємо розміри знизу вгору: діти завжди йдуть у списку після батьків
        acc = {}
        for path, depth, parent in reversed(order):
            own = self.own.get(path, 0) if depth <= self.MAX_DEPTH else self.own.pop(path, 0)
            total = own + acc.pop(path, 0)
            if depth <= self.MAX_DEPTH:
                self.sizes[path] = total
            if parent is not None:
                acc[parent] = acc.get(parent, 0) + total
        self.files = sorted(self.files, reverse=True)
        return self

    def _demo(self) -> "DiskScan":
        r = self.root.rstrip("\\/") or "C:"
        self.root = r
        tree = {r: [("Windows", 31.2), ("Program Files", 24.8), ("Program Files (x86)", 19.6), ("Users", 88.4),
                    ("ProgramData", 6.1), ("hiberfil.sys", 12.7), ("pagefile.sys", 8.0)],
                f"{r}\\Users": [("User", 87.9), ("Public", 0.5)],
                f"{r}\\Users\\User": [("AppData", 41.6), ("Downloads", 27.3), ("Videos", 12.2), ("Documents", 4.9),
                                      ("Desktop", 1.9)],
                f"{r}\\Users\\User\\AppData": [("Local", 33.1), ("Roaming", 7.8), ("LocalLow", 0.7)],
                f"{r}\\Program Files (x86)": [("Steam", 17.9), ("Microsoft", 1.1), ("Google", 0.6)]}
        for parent, kids in tree.items():
            self.children[parent] = []
            for name, gb in kids:
                p = f"{parent}\\{name}"
                if "." in name:  # файл
                    self.own[parent] = self.own.get(parent, 0) + int(gb * 2**30)
                    self.files.append((int(gb * 2**30), p))
                    continue
                self.children[parent].append(p)
                self.sizes[p] = int(gb * 2**30)
        for parent in tree:
            self.sizes[parent] = self.own.get(parent, 0) + sum(self.sizes.get(k, 0) for k in self.children[parent])
        self.files += [(int(9.4 * 2**30), f"{r}\\Users\\User\\Downloads\\Cyberpunk2077_backup.zip"),
                       (int(4.1 * 2**30), f"{r}\\Users\\User\\Videos\\2026-10-12 21-04-55.mkv"),
                       (int(2.8 * 2**30), f"{r}\\Users\\User\\Downloads\\Win11_25H2_Ukrainian_x64.iso")]
        self.files.sort(reverse=True)
        self.nfiles, self.ndirs = 412_580, 96_114
        return self

    def items(self, path: str) -> list:
        """Вміст папки: [(шлях, розмір, це_папка)] від найбільшого, плюс «файли в цій папці»."""
        out = [(k, self.sizes.get(k, 0), True) for k in self.children.get(path, [])]
        if self.own.get(path):
            out.append((path, self.own[path], False))
        return sorted(out, key=lambda x: -x[1])
