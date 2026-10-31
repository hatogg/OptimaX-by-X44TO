"""
OptimaX — «Монітор на телефоні»: сторінка з температурами, завантаженням і FPS, яку відкриваєш на телефоні в
домашній мережі (QR-код на ПК). Без встановлення додатка.

Безпека:
• лише читання, жодних дій з телефона;
• відповідає тільки адресам локальної мережі (10.x, 172.16–31.x, 192.168.x, 169.254.x, localhost) і лише за
  посиланням із секретним кодом (його видно тільки на ПК, у QR-коді);
• правило брандмауера Windows відкриває порт лише для локальної підмережі й лише в приватних мережах; вимкнення
  монітора правило видаляє (і видалення OptimaX — теж).
"""
from __future__ import annotations

import ctypes
import ipaddress
import json
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import engine as E
import features as F
from i18n import tr

PORT = 8765
RULE = "OptimaX Phone Monitor"
IDLE = 10  # стільки секунд без запитів — показники не збираються (і PresentMon зупиняється)


def settings() -> dict:
    p = dict(F.CFG["phone"] or {})
    if not p.get("token"):
        p["token"] = secrets.token_urlsafe(9)
        F.CFG["phone"] = p
    return p


def new_token() -> str:
    p = dict(F.CFG["phone"] or {})
    p["token"] = secrets.token_urlsafe(9)
    F.CFG["phone"] = p
    return p["token"]


def lan_ip() -> str:
    """IP цього ПК у домашній мережі: адреса інтерфейсу, через який іде маршрут назовні (пакети не надсилаються)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.168.255.255", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()
        if allowed(ip) and not ip.startswith("127."):
            return ip
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if allowed(ip) and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def allowed(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    return a.is_private or a.is_loopback or a.is_link_local


# ───────────────────────── показники ─────────────────────────
class _FT(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


class Stats:
    """Збирає показники раз на секунду, поки сторінку хтось дивиться."""

    def __init__(self):
        self.data = {"ts": 0}
        self.last_req = 0.0
        self.stop = threading.Event()
        self.cpu_prev = None
        self.nv = None
        self.pm = None  # PresentMon у режимі потоку: (процес, exe, [часи кадрів])
        self.fps = None
        self.thread = threading.Thread(target=self._run, name="phone-stats", daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        self._stop_pm()
        if self.nv:
            try:
                self.nv.close()
            except Exception:
                pass
            self.nv = None

    def touch(self) -> dict:
        self.last_req = time.time()
        return self.data

    def _cpu(self) -> float:
        if not E.IS_WIN:
            return 23.0
        idle, kern, user = _FT(), _FT(), _FT()
        ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user))

        def v(f):
            return (f.hi << 32) | f.lo
        cur = (v(idle), v(kern) + v(user))
        prev, self.cpu_prev = self.cpu_prev, cur
        if not prev or cur[1] - prev[1] <= 0:
            return 0.0
        return round(max(0.0, min(100.0, 100 * (1 - (cur[0] - prev[0]) / (cur[1] - prev[1])))), 1)

    def _ram(self) -> tuple:
        if not E.IS_WIN:
            return 41.0, 16.0
        s = E.mem_status()
        return float(s.dwMemoryLoad), round(s.ullTotalPhys / 2**30, 1)

    def _gpu(self) -> dict:
        if not E.IS_WIN:
            return dict(temp=63, util=71, clock=1708, power=96.5, vram_used=3900, vram_total=6144, name="P106-100")
        if self.nv is None:
            try:
                import gpubench as GB
                nv = GB.Nvml()
                self.nv = nv if nv.ok() else False
            except Exception:
                self.nv = False
        if not self.nv:
            return {}
        try:
            d = self.nv.read()
        except Exception:
            return {}
        return {k: d.get(k) for k in ("temp", "util", "clock", "power", "vram_used", "vram_total", "fan")}

    def _game(self) -> str:
        if not E.IS_WIN:
            return "cs2.exe" if E.DEMO else ""
        import library as LB
        import monitor as M
        fg = (M.foreground_process() or "").lower()
        return fg if fg in LB.known_exes() else ""

    # FPS: PresentMon пише кадри гри в stdout; рахуємо кадри за останню секунду
    def _start_pm(self, exe: str):
        import fpstest as FT
        pm = FT.find_presentmon()
        if not pm or not E.IS_WIN:
            return
        try:
            p = subprocess.Popen([pm, "--process_name", exe, "--output_stdout", "--no_console_stats",
                                  "--stop_existing_session", "--session_name", "OptimaXPhone"],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
                                 creationflags=E.CREATE_NO_WINDOW)
        except OSError:
            return
        frames: list = []
        self.pm = (p, exe, frames)
        threading.Thread(target=self._read_pm, args=(p, frames), daemon=True).start()

    def _read_pm(self, p, frames):
        col = None
        for line in p.stdout:
            cells = line.strip().split(",")
            if col is None:
                col = next((cells.index(c) for c in ("MsBetweenPresents", "FrameTime") if c in cells), None)
                continue
            try:
                frames.append((time.time(), float(cells[col])))
            except (ValueError, IndexError):
                continue
            if len(frames) > 2000:
                del frames[:1000]

    def _stop_pm(self):
        if self.pm:
            try:
                self.pm[0].kill()
            except OSError:
                pass
            self.pm = None

    def _fps(self, game: str):
        if not E.IS_WIN:
            return 117 if game else None
        if not game:
            self._stop_pm()
            return None
        if not self.pm or self.pm[1] != game or self.pm[0].poll() is not None:
            self._stop_pm()
            self._start_pm(game)
            return None
        now = time.time()
        recent = [ft for t, ft in self.pm[2] if now - t <= 1.5]
        if not recent:
            return None
        return round(1000 * len(recent) / sum(recent)) if sum(recent) > 0 else None

    def _run(self):
        import monitor as M
        temps = M.Pdh(array={"temp": r"\Thermal Zone Information(*)\Temperature"}) if E.IS_WIN else None
        while not self.stop.wait(1.0):
            if time.time() - self.last_req > IDLE:
                self._stop_pm()
                continue
            try:
                ram, ram_total = self._ram()
                zones = M._zone_c((temps.collect() if temps else {}).get("temp")) if E.IS_WIN else [48.0]
                game = self._game()
                self.data = dict(ts=int(time.time()), cpu=self._cpu(), cpu_temp=round(max(zones)) if zones else None,
                                 ram=ram, ram_total=ram_total, gpu=self._gpu(), game=game, fps=self._fps(game),
                                 booster=bool(F.BOOSTER.active))
            except Exception as e:  # показники не повинні валити сервер
                self.data = dict(self.data, error=f"{type(e).__name__}")
        if temps:
            temps.close()


# ───────────────────────── сторінка ─────────────────────────
PAGE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>OptimaX</title>
<style>
:root{{color-scheme:dark}}body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
background:#0E1118;color:#E8ECF4}}header{{padding:18px 18px 6px;display:flex;align-items:center;gap:10px}}
h1{{font-size:20px;margin:0}}#game{{color:#8B93A7;font-size:14px;padding:0 18px 10px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:6px 16px 20px}}
.c{{background:#171B25;border:1px solid #252B39;border-radius:16px;padding:14px}}
.k{{color:#8B93A7;font-size:13px}}.v{{font-size:34px;font-weight:700;margin-top:4px}}.u{{font-size:15px;color:#8B93A7}}
.wide{{grid-column:1/3}}.ok{{color:#3DD68C}}.warn{{color:#F5B83D}}.bad{{color:#F2555A}}
#st{{padding:0 18px 18px;color:#5D6578;font-size:12px}}
</style></head><body>
<header><h1>OptimaX</h1><span id="dot" class="k">●</span></header>
<div id="game"></div>
<div class="grid">
<div class="c wide"><div class="k">FPS</div><div class="v" id="fps">—</div></div>
<div class="c"><div class="k">{gpu_t}</div><div class="v" id="gt">—</div></div>
<div class="c"><div class="k">{gpu_l}</div><div class="v" id="gl">—</div></div>
<div class="c"><div class="k">{cpu_l}</div><div class="v" id="cl">—</div></div>
<div class="c"><div class="k">{cpu_t}</div><div class="v" id="ct">—</div></div>
<div class="c"><div class="k">{ram}</div><div class="v" id="rm">—</div></div>
<div class="c"><div class="k">{vram}</div><div class="v" id="vr">—</div></div>
<div class="c"><div class="k">{clock}</div><div class="v" id="ck">—</div></div>
<div class="c"><div class="k">{power}</div><div class="v" id="pw">—</div></div>
</div><div id="st"></div>
<script>
const T={{nog:{nog},game:{game},off:{off},boost:{boost}}};
function col(el,v,a,b){{el.className='v '+(v==null?'':v<a?'ok':v<b?'warn':'bad')}}
function put(id,v,u){{document.getElementById(id).innerHTML=(v==null?'—':v)+(v!=null&&u?' <span class="u">'+u+'</span>':'')}}
async function tick(){{try{{const r=await fetch('api',{{cache:'no-store'}});const d=await r.json();const g=d.gpu||{{}};
put('fps',d.fps);put('gt',g.temp,'°C');col(document.getElementById('gt'),g.temp,75,85);
put('gl',g.util,'%');put('cl',d.cpu==null?null:Math.round(d.cpu),'%');put('ct',d.cpu_temp,'°C');
col(document.getElementById('ct'),d.cpu_temp,75,88);
put('rm',d.ram==null?null:Math.round(d.ram),'%');put('vr',g.vram_used==null?null:(g.vram_used/1024).toFixed(1),
g.vram_total?'/ '+(g.vram_total/1024).toFixed(1)+' GB':'GB');put('ck',g.clock,'MHz');
put('pw',g.power==null?null:Math.round(g.power),'W');
document.getElementById('game').textContent=d.game?T.game+' '+d.game+(d.booster?' · '+T.boost:''):T.nog;
document.getElementById('dot').className='ok';document.getElementById('st').textContent=new Date().toLocaleTimeString();
}}catch(e){{document.getElementById('dot').className='bad';document.getElementById('st').textContent=T.off}}}}
tick();setInterval(tick,1500);
</script></body></html>"""


def page_html() -> str:
    import i18n
    js = lambda s: json.dumps(s, ensure_ascii=False)  # noqa: E731
    return PAGE.format(lang=i18n.LANG, gpu_t=tr("ph.gpu_t"), gpu_l=tr("ph.gpu_l"), cpu_l=tr("ph.cpu_l"),
                       cpu_t=tr("ph.cpu_t"), ram=tr("ph.ram"), vram=tr("ph.vram"), clock=tr("ph.clock"),
                       power=tr("ph.power"), nog=js(tr("ph.no_game")), game=js(tr("ph.game")),
                       off=js(tr("ph.offline")), boost=js(tr("ph.boost")))


class _Handler(BaseHTTPRequestHandler):
    server_version = "OptimaX"
    sys_version = ""

    def log_message(self, *a):  # без журналу запитів у консоль
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        mon = self.server.monitor
        if not allowed(self.client_address[0]):
            self.close_connection = True
            return
        parts = [p for p in self.path.split("?", 1)[0].split("/") if p]
        if not parts or not secrets.compare_digest(parts[0].encode("utf-8", "replace"), mon.token.encode("utf-8")):
            self._send(404, b"not found", "text/plain")
            return
        if len(parts) == 1:
            if not self.path.split("?", 1)[0].endswith("/"):  # відносний шлях «api» має працювати
                self.send_response(301)
                self.send_header("Location", f"/{mon.token}/")
                self.end_headers()
                return
            self._send(200, page_html().encode("utf-8"), "text/html; charset=utf-8")
        elif parts[1:] == ["api"]:
            self._send(200, json.dumps(mon.stats.touch()).encode("utf-8"), "application/json")
        else:
            self._send(404, b"not found", "text/plain")


class Monitor:
    def __init__(self):
        self.httpd = None
        self.stats = None
        self.token = ""
        self.port = 0
        self.ip = ""

    @property
    def running(self) -> bool:
        return self.httpd is not None

    def url(self) -> str:
        return f"http://{self.ip}:{self.port}/{self.token}/" if self.running else ""

    def start(self, log=lambda *_: None) -> dict:
        if self.running:
            return {"ok": 1, "url": self.url()}
        st = settings()
        self.token = st["token"]
        err = None
        for port in range(int(st.get("port") or PORT), int(st.get("port") or PORT) + 10):
            try:
                httpd = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
                break
            except OSError as e:
                err = e
        else:
            return {"error": str(err)}
        httpd.daemon_threads = True
        httpd.monitor = self
        self.httpd, self.port, self.ip = httpd, port, lan_ip()
        self.stats = Stats()
        self.stats.start()
        threading.Thread(target=httpd.serve_forever, name="phone-http", daemon=True).start()
        firewall(True, port, log)
        p = dict(F.CFG["phone"] or {})
        p.update(enabled=True, port=port)
        F.CFG["phone"] = p
        return {"ok": 1, "url": self.url(), "public": public_network()}

    def stop(self, log=lambda *_: None, remember: bool = True) -> dict:
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.stats:
            self.stats.close()
            self.stats = None
        if remember:
            firewall(False, self.port, log)
            p = dict(F.CFG["phone"] or {})
            p["enabled"] = False
            F.CFG["phone"] = p
        return {"ok": 1}


MONITOR = Monitor()


# ───────────────────────── брандмауер ─────────────────────────
def firewall(on: bool, port: int, log=lambda *_: None) -> None:
    if not E.IS_WIN or E.DRY_RUN:
        log(f"  [dry-run] netsh advfirewall firewall {'add' if on else 'delete'} rule name=\"{RULE}\"")
        return
    E.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={RULE}"], 15)
    if on:
        # правило саме для OptimaX: без програми в правилі Windows ще й запитала б «дозволити доступ?», а «Скасувати»
        # там створює правило блокування, сильніше за наше
        E.run(["netsh", "advfirewall", "firewall", "add", "rule", f"name={RULE}", "dir=in", "action=allow",
               f"program={sys.executable}", "protocol=TCP", f"localport={port}", "profile=private",
               "remoteip=localsubnet"], 15, log)


def public_network() -> bool:
    """Мережа позначена в Windows як «Загальнодоступна» — правило для приватних мереж не діє, телефон не підключиться."""
    if not E.IS_WIN:
        return False
    data = E.ps_json("@(Get-NetConnectionProfile | ForEach-Object { [int]$_.NetworkCategory }) | ConvertTo-Json "
                     "-Compress", 20)
    cats = [int(x) for x in E.as_list(data) if str(x).isdigit()]
    return bool(cats) and all(c == 0 for c in cats)  # 0 — Public, 1 — Private, 2 — Domain


def qr_matrix(url: str) -> list:
    import qr
    return qr.encode(url)


def cleanup() -> None:
    """Видалення OptimaX: прибрати правило брандмауера."""
    if E.IS_WIN and not E.DRY_RUN:
        E.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={RULE}"], 15)


def demo_url() -> str:
    return f"http://192.168.1.23:{PORT}/{settings()['token']}/"
