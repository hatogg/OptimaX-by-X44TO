"""
OptimaX — FPS-оверлей в іграх.

Як це працює, і чого тут навмисно немає:
• Жодної DLL-ін'єкції та перехоплення Present у процесі гри: це ризик бану від античитів (Vanguard, EasyAntiCheat,
  BattlEye, FACEIT). FPS і час кадру OptimaX бере з PresentMon (ETW, відкритий інструмент Intel, MIT), який дивиться на
  події системи ззовні, як і «Чому лагає?».
• Оверлей — окреме прозоре вікно поверх гри: завжди зверху, пропускає кліки, не забирає фокус і не з'являється в Alt+Tab
  (Qt: Tool | Frameless | StaysOnTop | TransparentForInput | DoesNotAcceptFocus; Windows: WS_EX_LAYERED | TRANSPARENT |
  TOPMOST | TOOLWINDOW | NOACTIVATE). З'являється на тому моніторі, де гра.
• У справжньому монопольному повноекранному режимі (PresentMode «Hardware: Legacy Flip») зовнішнє вікно не видно — це
  визначається з подій PresentMon, і OptimaX радить безрамковий режим. Оверлей може перевести гру з Independent Flip у
  Composed: Flip (трохи більша затримка) — режим показу видно в розширеному вигляді, а зміна після появи оверлея
  записується й показується один раз.
• Гра визначається сама: вікно на передньому плані на весь монітор, процес якого є серед ігор бібліотеки / «Моїх ігор»
  або виводить кадри (PresentMon). Над браузерами, провідником і робочим столом не показується; білий і чорний списки.

Датчики — ті самі, що в Hardware Center (hwtests.Sensors: лічильники Windows і NVML), раз на секунду; числа на екрані
оновлюються 4 рази на секунду. Запис сесії (гаряча клавіша) зберігає кадри й датчики в JSON/CSV, а після зупинки —
звіт: FPS, 1% / 0.1% low, фризи, фонові процеси (procmon) і висновок «Чому лагає?» (perfdiag).
"""
from __future__ import annotations

import collections
import csv
import ctypes
import io
import json
import os
import subprocess
import threading
import time

import engine as E

MODES = ("minimal", "standard", "extended")
CORNERS = ("tl", "tr", "bl", "br")
WINDOW_S = 10.0  # FPS / 1% low / 0.1% low — за останні 10 секунд
UPDATE_MS = 250
SENSOR_S = 1.0
SHOW_DELAY_S = 1.5
HOTKEY_PRESETS = (
    ("Ctrl+Shift+F10", 0x0002 | 0x0004, 0x79, "Ctrl+Shift+F11", 0x0002 | 0x0004, 0x7A),
    ("Alt+F10", 0x0001, 0x79, "Alt+F11", 0x0001, 0x7A),
    ("Ctrl+Alt+O", 0x0002 | 0x0001, ord("O"), "Ctrl+Alt+R", 0x0002 | 0x0001, ord("R")),
)
NEVER = {"explorer.exe", "chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe", "vivaldi.exe",
         "optimax.exe", "python.exe", "pythonw.exe", "steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe",
         "discord.exe", "obs64.exe", "searchhost.exe", "startmenuexperiencehost.exe", "shellexperiencehost.exe",
         "lockapp.exe", "textinputhost.exe", "applicationframehost.exe", "code.exe", "devenv.exe", "taskmgr.exe",
         "vlc.exe", "mpc-hc64.exe", "mpc-hc.exe", "potplayermini64.exe", "wmplayer.exe", "video.ui.exe",
         "powerpnt.exe", "scrnsave.scr", "logonui.exe"}
EXCLUSIVE = ("legacy flip", "legacy copy")
SESSIONS_DIR = os.path.join(E.DATA_DIR, "sessions")
PAUSED = threading.Event()  # тест FPS «до і після» чи розумна оптимізація міряє гру: оверлей ховається, щоб не впливати


# ───────────────────────── кадри: статистика за вікно ─────────────────────────
def window_stats(frames, now: float = None) -> dict:
    """frames — [(час, мс)] за останні WINDOW_S секунд -> {fps (за 1 с), avg, low1, low01, ft (останній кадр)}."""
    fr = list(frames)
    if not fr:
        return {}
    now = now or fr[-1][0]
    last = [ms for t, ms in fr if now - t <= 1.0]
    ms_all = [ms for _t, ms in fr if 0.05 < ms < 1000]
    if not ms_all:
        return {}
    s = sorted(ms_all, reverse=True)
    w1 = s[:max(1, len(s) // 100)]
    w01 = s[:max(1, len(s) // 1000)]
    span = sum(ms_all) / 1000
    return dict(fps=round(len(last) if last else 1000 / ms_all[-1], 0), avg=round(len(ms_all) / span, 1) if span else 0.0,
                low1=round(1000 / (sum(w1) / len(w1)), 1), low01=round(1000 / (sum(w01) / len(w01)), 1),
                ft=round(ms_all[-1], 2))


def is_exclusive(mode: str) -> bool:
    m = (mode or "").lower()
    return any(x in m for x in EXCLUSIVE)


def flip_downgrade(before: str, after: str) -> bool:
    """Гра вийшла з Independent Flip у Composed після появи оверлея."""
    return "independent flip" in (before or "").lower() and "composed" in (after or "").lower() and \
        "independent" not in (after or "").lower()


class CsvRows:
    """Рядки CSV PresentMon, що приходять потоком (--output_stdout): заголовок, потім кадри."""

    def __init__(self):
        self.cols = None

    def feed(self, line: str):
        """-> (мс, режим показу, PID, ім'я процесу) або None."""
        line = line.strip()
        if not line:
            return None
        row = next(csv.reader(io.StringIO(line)))
        if self.cols is None or (row and row[0] == "Application"):
            self.cols = {h.strip(): i for i, h in enumerate(row)}
            return None
        c = self.cols
        idx = next((c[k] for k in ("MsBetweenPresents", "FrameTime", "msBetweenPresents") if k in c), None)
        if idx is None or idx >= len(row):
            return None
        try:
            ms = float(row[idx])
        except ValueError:
            return None
        mode = row[c["PresentMode"]] if "PresentMode" in c and c["PresentMode"] < len(row) else ""
        pid = row[c["ProcessID"]] if "ProcessID" in c and c["ProcessID"] < len(row) else ""
        app = row[c["Application"]] if "Application" in c and c["Application"] < len(row) else ""
        return ms, mode, pid, app


class Stream:
    """PresentMon для одного процесу гри: потік читає кадри, вікно останніх WINDOW_S секунд — у self.frames."""

    def __init__(self, pm: str, pid: int):
        self.pid = pid
        self.frames = collections.deque()
        self.mode = ""
        self.modes = collections.Counter()
        self.recording = None  # [(t, мс)] під час запису сесії
        self.lock = threading.Lock()
        self.proc = subprocess.Popen(
            [pm, "--process_id", str(pid), "--output_stdout", "--no_console_stats", "--stop_existing_session",
             "--session_name", "OptimaXOverlay", "--terminate_on_proc_exit"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=E.CREATE_NO_WINDOW)
        self.thread = threading.Thread(target=self._read, name="OptimaX overlay frames", daemon=True)
        self.thread.start()

    def _read(self) -> None:
        rows = CsvRows()
        for raw in iter(self.proc.stdout.readline, b""):
            got = rows.feed(raw.decode("utf-8", "replace"))
            if not got:
                continue
            ms, mode, _pid, _app = got
            now = time.time()
            with self.lock:
                self.frames.append((now, ms))
                while self.frames and now - self.frames[0][0] > WINDOW_S:
                    self.frames.popleft()
                if mode:
                    self.mode = mode
                    self.modes[mode] += 1
                if self.recording is not None and len(self.recording) < 2_000_000:
                    self.recording.append((round(now, 4), ms))

    def stats(self) -> dict:
        with self.lock:
            return window_stats(self.frames, time.time())

    def series(self, n: int = 240) -> list:
        with self.lock:
            return [ms for _t, ms in list(self.frames)[-n:]]

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


class DemoStream:
    """Поза Windows: кадри гри з невеликими фризами для інтерфейсу й тестів."""

    def __init__(self, pm: str = "", pid: int = 0):
        import random
        self.pid = pid
        self.rnd = random.Random(7)
        self.frames = collections.deque()
        self.mode = "Hardware: Independent Flip"
        self.modes = collections.Counter({self.mode: 1})
        self.recording = None
        self.t = time.time() - WINDOW_S
        self.lock = threading.Lock()
        self._fill()

    def _fill(self) -> None:
        now = time.time()
        base = {"laptop": 9.5, "old": 30.0}.get(E.DEMO, 6.3)
        while self.t < now:
            ms = base * self.rnd.uniform(0.92, 1.1) * (3.2 if self.rnd.random() < 0.004 else 1.0)
            self.t += ms / 1000
            self.frames.append((self.t, ms))
            if self.recording is not None:
                self.recording.append((round(self.t, 4), ms))
        while self.frames and now - self.frames[0][0] > WINDOW_S:
            self.frames.popleft()

    def stats(self) -> dict:
        self._fill()
        return window_stats(self.frames, time.time())

    def series(self, n: int = 240) -> list:
        self._fill()
        return [ms for _t, ms in list(self.frames)[-n:]]

    alive = True

    def stop(self) -> None:
        pass


# ───────────────────────── яке вікно — гра ─────────────────────────
class _RECT(ctypes.Structure):
    _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]


class _MI(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_ulong), ("mon", _RECT), ("work", _RECT), ("flags", ctypes.c_ulong)]


def foreground() -> dict:
    """{pid, exe, rect: (l, t, r, b), monitor: (l, t, r, b), full: вікно на весь монітор} або {}."""
    if not E.IS_WIN:
        return {}
    u = ctypes.windll.user32
    u.GetForegroundWindow.restype = ctypes.c_void_p
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return {}
    pid = ctypes.c_ulong(0)
    u.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    r = _RECT()
    u.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
    u.MonitorFromWindow.restype = ctypes.c_void_p
    mon = u.MonitorFromWindow(ctypes.c_void_p(hwnd), 2)  # MONITOR_DEFAULTTONEAREST
    mi = _MI()
    mi.cb = ctypes.sizeof(mi)
    u.GetMonitorInfoW(ctypes.c_void_p(mon), ctypes.byref(mi))
    m = mi.mon
    path = E.process_path(pid.value) or ""
    exe = path.replace("/", "\\").rsplit("\\", 1)[-1].lower()
    full = r.l <= m.l and r.t <= m.t and r.r >= m.r and r.b >= m.b
    return dict(pid=pid.value, exe=exe, rect=(r.l, r.t, r.r, r.b), monitor=(m.l, m.t, m.r, m.b), full=full, hwnd=hwnd)


def is_game(fg: dict, known: set, cfg: dict) -> bool:
    """Чи показувати оверлей над цим вікном."""
    exe = (fg or {}).get("exe") or ""
    if not exe:
        return False
    white = {x.lower() for x in cfg.get("white") or []}
    black = {x.lower() for x in cfg.get("black") or []} | NEVER
    if exe in white:
        return True
    if exe in black:
        return False
    if exe in known:
        return True
    return bool(cfg.get("auto", True) and fg.get("full"))  # невідома програма на весь монітор — найімовірніше гра


def known_games() -> set:
    try:
        import features as F
        import library as LB
        import ntpath
        names = set(LB.known_exes())
        names |= {ntpath.basename(g["path"]).lower() for g in F.CFG["games"] or []}
        names |= set((F.CFG["game_exes"] or {}).get("names") or [])
        return {n.lower() for n in names}
    except Exception:
        return set()


def render_gpu(pid: int) -> str:
    """Яка відеокарта малює гру: драйвер, завантажений процесом (gpuinfo.render_path), -> назва адаптера."""
    try:
        import gpuinfo as GI
        import gpuselect as GS
        path = GI.render_path(GI.process_modules(pid))
        drv = [v for v in (path.get("drivers") or {}) if v != "warp"]
        if len(drv) != 1:
            return ""
        ads = [a for a in GS.adapters(GS.cached_probe() or {}) if a.get("vendor") == drv[0]]
        return ads[0]["name"] if len(ads) == 1 else drv[0].upper()
    except Exception:
        return ""


def overlay_lines(mode: str, st: dict, s: dict, extra: dict) -> list:
    """Рядки оверлея: [(текст, колір: main | dim | warn)]."""
    def n(v, fmt="{:.0f}"):
        return "—" if v is None else fmt.format(v)
    fps = st.get("fps")
    out = [(f"{n(fps)} FPS", "main")]
    if mode == "minimal":
        return out
    out.append((f"1% {n(st.get('low1'))} · 0.1% {n(st.get('low01'))} · {n(st.get('ft'), '{:.1f}')} ms", "dim"))
    out.append((f"CPU {n(s.get('util'))}%" + (f" · {n(s.get('temp'))}°C" if s.get("temp") is not None else ""), "dim"))
    if s.get("gpu_util") is not None or s.get("gpu_temp") is not None:
        out.append((f"GPU {n(s.get('gpu_util'))}%" + (f" · {n(s.get('gpu_temp'))}°C" if s.get("gpu_temp") is not None
                                                       else ""), "dim"))
    if mode == "extended":
        if s.get("mhz") or s.get("gpu_clock"):
            out.append((f"{n(s.get('mhz'))} / {n(s.get('gpu_clock'))} MHz", "dim"))
        if s.get("vram_used") is not None:
            out.append((f"VRAM {s['vram_used'] / 1024:.1f}/{(s.get('vram_total') or 0) / 1024:.1f} GB", "dim"))
        if s.get("ram_used") is not None:
            out.append((f"RAM {s['ram_used']:.1f}/{s.get('ram_total') or 0:.0f} GB", "dim"))
        if s.get("gpu_power"):
            out.append((f"{s['gpu_power']:.0f} W", "dim"))
        if extra.get("gpu"):
            out.append((extra["gpu"], "dim"))
        if extra.get("mode"):
            out.append((extra["mode"], "warn" if is_exclusive(extra["mode"]) or "composed" in extra["mode"].lower()
                        else "dim"))
    return out


# ───────────────────────── запис сесії ─────────────────────────
def session_report(frames: list, samples: list, game: str, start: float, procs: dict = None) -> dict:
    """Кадри й датчики сесії -> звіт (fpstest.stats, фризи, «Чому лагає?» з perfdiag)."""
    import fpstest as FT
    ms = [x for _t, x in frames]
    st = FT.stats(ms) or {}
    per_sec = []
    if frames:
        t0 = frames[0][0]
        buckets = collections.defaultdict(int)
        for t, _x in frames:
            buckets[int(t - t0)] += 1
        per_sec = [buckets.get(i, 0) for i in range(int(frames[-1][0] - t0) + 1)]
    spikes = []
    if ms:
        med = sorted(ms)[len(ms) // 2]
        spikes = [round(t - frames[0][0], 2) for t, x in frames if x > 2.5 * med][:200]
    import perfdiag as PD
    diag = PD.diagnose(samples, st, {}, procs or {})
    return dict(game=game, start=int(start), seconds=st.get("seconds", 0), stats={k: v for k, v in st.items()
                                                                                    if k != "series"},
                fps_series=per_sec, spikes=spikes, sensors=samples[-1800:], procs=procs or {}, diag=diag)


def save_session(rep: dict, frames: list) -> str:
    """JSON зі звітом і CSV з кадрами в %APPDATA%\\OptimaX\\sessions -> шлях до JSON."""
    folder = SESSIONS_DIR or os.path.join(os.path.expanduser("~"), "OptimaX-sessions")
    os.makedirs(folder, exist_ok=True)
    stem = os.path.join(folder, time.strftime("%Y%m%d-%H%M%S", time.localtime(rep.get("start") or time.time())) +
                        "-" + (rep.get("game") or "game").replace(".exe", ""))
    with open(stem + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time_s", "frametime_ms"])
        t0 = frames[0][0] if frames else 0
        for t, ms in frames:
            w.writerow([round(t - t0, 4), round(ms, 3)])
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False)
    return stem + ".json"


def self_cpu_percent(prev: tuple = None) -> tuple:
    """Частка процесора самого OptimaX між двома викликами -> (відсоток або None, стан для наступного виклику)."""
    import monitor as M
    t = time.perf_counter()
    cur = M._proc_time(os.getpid()) if E.IS_WIN else None
    if cur is None or not prev:
        return None, (t, cur)
    dt = (t - prev[0]) * 1e7 * M.cpu_count()
    return (round(100 * (cur - prev[1]) / dt, 2) if dt > 0 and prev[1] is not None else None), (t, cur)
