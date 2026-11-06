"""
OptimaX Hardware Center — перевірка відеопам'яті (VRAM).

Окремий процес (OptimaX.exe --vram-test …) створює контекст OpenGL на вибраній відеокарті (той самий вибір і ті самі
способи, що й у GPU-тесті, gpuselect.py), виділяє буфери по 64 МБ, поки не набере потрібний обсяг або драйвер не скаже
GL_OUT_OF_MEMORY, і для кожного шаблону (нулі, одиниці, шахівниця, біжуча одиниця, випадкові дані, номер блока):
записує шаблон у всі буфери → копіює кожен буфер засобами відеокарти в контрольний буфер (glCopyBufferSubData, тобто
дані мусять пройти через пам'ять карти) → читає назад і звіряє до байта.

Чесні межі:
• Уся VRAM не перевіряється ніколи: частину займають Windows, драйвер і відкриті програми. Тест бере частку вільної
  пам'яті (за NVX_gpu_memory_info / ATI_meminfo, інакше — за обсягом карти) і лишає запас.
• Драйвер OpenGL сам вирішує, де лежить буфер; під тиском він може тримати частину в системній пам'яті. Перевірено
  «N МБ буферів відеокарти», а не «N МБ мікросхем».
• Вбудована графіка не має власної VRAM: її буфери — це оперативна пам'ять, тож для неї тест обмежено 512 МБ.
"""
from __future__ import annotations

import ctypes
import json
import os
import random
import sys
import tempfile
import time

import engine as E
from i18n import tr

CHUNK = 64 << 20
BLOCK = 1 << 20
RESERVE_MB = 512
IGPU_MAX_MB = 512
CHOICES = (25, 50, 75)  # % вільної відеопам'яті

GL_ARRAY_BUFFER = 0x8892
GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER = 0x8F36, 0x8F37
GL_STATIC_DRAW = 0x88E4
GL_OUT_OF_MEMORY = 0x0505
GL_RENDERER, GL_VENDOR, GL_VERSION = 0x1F01, 0x1F00, 0x1F02
GL_GPU_MEM_TOTAL_NVX, GL_GPU_MEM_AVAIL_NVX = 0x9048, 0x9049
GL_TEXTURE_FREE_MEMORY_ATI = 0x87FC

_e, _i, _u, _p, _sz = ctypes.c_uint, ctypes.c_int, ctypes.c_uint, ctypes.c_void_p, ctypes.c_ssize_t
_SIGS = {
    "glGetError": (_e,),
    "glGetString": (ctypes.c_char_p, _e),
    "glGetIntegerv": (None, _e, ctypes.POINTER(_i)),
    "glGenBuffers": (None, _i, ctypes.POINTER(_u)),
    "glDeleteBuffers": (None, _i, ctypes.POINTER(_u)),
    "glBindBuffer": (None, _e, _u),
    "glBufferData": (None, _e, _sz, _p, _e),
    "glBufferSubData": (None, _e, _sz, _sz, _p),
    "glGetBufferSubData": (None, _e, _sz, _sz, _p),
    "glCopyBufferSubData": (None, _e, _e, _sz, _sz, _sz),
    "glFinish": (None,),
}


class GLB:
    """Функції OpenGL для роботи з буферами (адреси дає Qt або EGL)."""

    def __init__(self, getproc):
        functype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
        legacy = None
        if E.IS_WIN:
            try:
                legacy = ctypes.WinDLL("opengl32")
            except OSError:
                legacy = None
        for name, sig in _SIGS.items():
            addr = 0
            try:
                addr = int(getproc(name.encode()) or 0)
            except Exception:
                addr = 0
            if addr in (0, 1, 2, 3, -1) and legacy is not None:
                try:
                    addr = ctypes.cast(getattr(legacy, name), ctypes.c_void_p).value or 0
                except AttributeError:
                    addr = 0
            if not addr:
                raise RuntimeError(f"OpenGL: {name}")
            setattr(self, name, functype(*sig)(addr))

    def info(self) -> dict:
        get = lambda k: (self.glGetString(k) or b"").decode("utf-8", "replace")  # noqa: E731
        return dict(renderer=get(GL_RENDERER), vendor=get(GL_VENDOR), version=get(GL_VERSION))

    def free_mb(self) -> int:
        """Вільна відеопам'ять за розширенням драйвера (NVIDIA / AMD) або 0, якщо драйвер не каже."""
        v = (ctypes.c_int * 4)()
        while self.glGetError():
            pass
        for enum in (GL_GPU_MEM_AVAIL_NVX, GL_TEXTURE_FREE_MEMORY_ATI):
            v[0] = 0
            self.glGetIntegerv(enum, v)
            if not self.glGetError() and v[0] > 0:
                return int(v[0]) // 1024  # КБ -> МБ
        return 0


def patterns(seed: int = 9) -> list:
    """[(назва, блок 1 МБ або None — «номер блока в блоці»)]."""
    walk = bytes(1 << (i % 8) for i in range(64))
    return [("zeros", b"\x00" * BLOCK), ("ones", b"\xff" * BLOCK), ("checker", b"\xaa\x55" * (BLOCK // 2)),
            ("walking", walk * (BLOCK // len(walk))), ("random", random.Random(seed).randbytes(BLOCK)),
            ("address", None)]


def _addr_chunk(ci: int) -> bytes:
    tag = (ci * 7919 + 1).to_bytes(8, "little") + b"OptimaXV"
    return tag * (CHUNK // 16)


def plan_mb(free_mb: int, total_mb: int, pct: int, integrated: bool) -> int:
    """Скільки МБ перевірити: pct% вільної (або загальної, якщо вільну не дізнатися) мінус запас; кратно 64 МБ."""
    base = free_mb or total_mb
    mb = int(base * max(5, min(90, pct)) / 100)
    mb = min(mb, max(0, base - RESERVE_MB)) if base > RESERVE_MB * 2 else mb // 2
    if integrated:
        mb = min(mb, IGPU_MAX_MB)
    return max(64, mb - mb % 64)


class Core:
    """Сам тест на готовому контексті OpenGL. step() — по одному буферу, щоб процес міг оновлювати стан і зупинятися."""

    def __init__(self, gl: GLB, target_mb: int, seed: int = 9):
        self.gl = gl
        self.target = max(64, target_mb)
        self.bufs = []
        self.scratch = None
        self.errors = 0
        self.bad_bytes = 0
        self.log = []
        self.oom = False
        self.pats = patterns(seed)

    def _err(self) -> int:
        e = self.gl.glGetError()
        while self.gl.glGetError():
            pass
        return e

    def _new(self, data: bytes = None) -> int:
        gl = self.gl
        ids = (ctypes.c_uint * 1)()
        gl.glGenBuffers(1, ids)
        gl.glBindBuffer(GL_COPY_WRITE_BUFFER, ids[0])
        gl.glBufferData(GL_COPY_WRITE_BUFFER, CHUNK, None, GL_STATIC_DRAW)
        if data is not None:
            gl.glBufferSubData(GL_COPY_WRITE_BUFFER, 0, CHUNK, data)
        gl.glFinish()
        if self._err() == GL_OUT_OF_MEMORY or not ids[0]:
            gl.glDeleteBuffers(1, ids)
            raise MemoryError
        return ids[0]

    def allocate(self, progress=None, should_stop=None) -> int:
        """Буфери по 64 МБ до цілі або до GL_OUT_OF_MEMORY. Кожен одразу заповнюється — драйвер не відкладе виділення."""
        fill = b"\x00" * CHUNK
        try:
            self.scratch = self._new(fill)
            while len(self.bufs) * 64 < self.target:
                if should_stop and should_stop():
                    break
                self.bufs.append(self._new(fill))
                if progress:
                    progress(len(self.bufs) * 64)
        except MemoryError:
            self.oom = True
        return len(self.bufs) * 64

    def write(self, pi: int, ci: int) -> None:
        name, blk = self.pats[pi]
        data = _addr_chunk(ci) if blk is None else blk * (CHUNK // BLOCK)
        self.gl.glBindBuffer(GL_COPY_WRITE_BUFFER, self.bufs[ci])
        self.gl.glBufferSubData(GL_COPY_WRITE_BUFFER, 0, CHUNK, data)

    def verify(self, pi: int, ci: int) -> int:
        """Буфер ci -> (копія відеокартою) контрольний буфер -> читання -> звірка. -> кількість поганих блоків 1 МБ."""
        gl = self.gl
        name, blk = self.pats[pi]
        gl.glBindBuffer(GL_COPY_READ_BUFFER, self.bufs[ci])
        gl.glBindBuffer(GL_COPY_WRITE_BUFFER, self.scratch)
        gl.glCopyBufferSubData(GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER, 0, 0, CHUNK)
        out = ctypes.create_string_buffer(CHUNK)
        gl.glGetBufferSubData(GL_COPY_WRITE_BUFFER, 0, CHUNK, out)
        got = out.raw
        want = _addr_chunk(ci) if blk is None else None
        bad = 0
        for bi in range(CHUNK // BLOCK):
            o = bi * BLOCK
            w = want[o:o + BLOCK] if want is not None else blk
            if got[o:o + BLOCK] != w:
                bad += 1
                nb = sum(1 for x, y in zip(got[o:o + BLOCK], w) if x != y)
                self.bad_bytes += nb
                if len(self.log) < 20:
                    self.log.append(dict(pattern=name, chunk=ci, block=bi, bytes=nb))
        self.errors += bad
        return bad

    def release(self) -> None:
        ids = self.bufs + ([self.scratch] if self.scratch else [])
        if ids:
            arr = (ctypes.c_uint * len(ids))(*ids)
            self.gl.glDeleteBuffers(len(ids), arr)
        self.bufs, self.scratch = [], None


def run_core(core: Core, state: dict, write_state, should_stop) -> None:
    """Повний прохід: виділення, потім для кожного шаблону — запис усіх буферів, звірка кожного."""
    state.update(state="allocating")
    write_state()
    got = core.allocate(lambda mb: (state.__setitem__("alloc_mb", mb), write_state()), should_stop)
    state.update(state="running", mb=got, oom=core.oom, total=len(core.pats) * 2 * len(core.bufs), done=0)
    write_state()
    for pi in range(len(core.pats)):
        state["pattern"] = core.pats[pi][0]
        for phase in ("write", "verify"):
            for ci in range(len(core.bufs)):
                if should_stop():
                    state["state"] = "cancelled"
                    return
                if phase == "write":
                    core.write(pi, ci)
                else:
                    core.verify(pi, ci)
                state["done"] += 1
                state.update(errors=core.errors, bad_bytes=core.bad_bytes)
                write_state()
            core.gl.glFinish()
    state.update(state="done", errors=core.errors, bad_bytes=core.bad_bytes, log=core.log)


# ───────────────────────── окремий процес ─────────────────────────
def _arg(argv, name: str, default: str = "") -> str:
    for a in argv:
        if a.startswith(f"--{name}="):
            return a.split("=", 1)[1]
    return default


def _write(path: str, data: dict) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


def run_child(argv) -> int:
    """OptimaX.exe --vram-test --pct=50 --out=<json> [--want-name=… --want-vendor=… --vram-mb=… --igpu=1]"""
    import gpubench as GB
    mesa = GB.load_mesa(_arg(argv, "mesa", ""))
    out = _arg(argv, "out") or os.path.join(tempfile.gettempdir(), "optimax-vram.json")
    pct = int(_arg(argv, "pct", "50") or 50)
    total_mb = int(_arg(argv, "vram-mb", "0") or 0)
    igpu = _arg(argv, "igpu", "") == "1"
    want = dict(name=_arg(argv, "want-name", ""), vendor=_arg(argv, "want-vendor", ""))
    state = dict(state="starting", kind="vram", pid=os.getpid(), mesa=mesa, t=0.0)
    _write(out, state)
    t0 = time.time()
    from PyQt6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QGuiApplication(sys.argv[:1])
    surf = QOffscreenSurface()
    surf.setFormat(fmt)
    surf.create()
    ctx = QOpenGLContext()
    ctx.setFormat(fmt)
    if not ctx.create() or not ctx.makeCurrent(surf):
        state.update(state="error", error="OpenGL 3.3 context")
        _write(out, state)
        return 1
    try:
        gl = GLB(lambda n: int(ctx.getProcAddress(n) or 0))
        info = gl.info()
        state.update(renderer=info["renderer"], vendor=info["vendor"], gl=info["version"])
        if want["name"]:
            import gpuselect as GS
            state["render_match"] = GS.render_match(want, info["vendor"], info["renderer"])
        free = gl.free_mb()
        state["free_mb"] = free
        target = plan_mb(free, total_mb, pct, igpu)
        state["target_mb"] = target
        core = Core(gl, target)

        def write_state():
            state["t"] = round(time.time() - t0, 1)
            _write(out, state)
        try:
            run_core(core, state, write_state, lambda: os.path.exists(out + ".stop"))
        finally:
            core.release()
    except Exception as e:  # noqa: BLE001
        state.update(state="error", error=f"{type(e).__name__}: {e}"[:300])
    state["t"] = round(time.time() - t0, 1)
    _write(out, state)
    ctx.doneCurrent()
    del app
    return 0


class Run:
    """Запуск перевірки VRAM з програми (план вибору карти — gpuselect)."""

    def __init__(self, pct: int, adapter: dict = None, vram_mb: int = 0, igpu: bool = False):
        import gpubench as GB
        import gpuselect as GS
        self.adapter = dict(adapter or {})
        self.out = os.path.join(tempfile.gettempdir(), f"optimax-vram-{os.getpid()}-{int(time.time() * 1000)}.json")
        cmd = GB.self_command() + ["--vram-test", f"--out={self.out}", f"--pct={pct}", f"--vram-mb={int(vram_mb)}",
                                   f"--igpu={1 if igpu else 0}"]
        args, _env, mesa = GB._plan_args(self.adapter, "")
        cmd += args
        if mesa:
            cmd.append(f"--mesa={mesa}")
        env = GS.child_env(self.adapter)
        here = None if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
        import subprocess
        self.proc = subprocess.Popen(cmd, cwd=here, env=env)
        self.stopped = False

    def poll(self) -> dict:
        try:
            with open(self.out, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {"state": "starting"}
        rc = self.proc.poll()
        if rc is not None and data.get("state") not in ("done", "error", "cancelled"):
            data = dict(data, state="cancelled" if self.stopped else "crash", exit_code=rc)
        return data

    @property
    def alive(self) -> bool:
        return self.proc.poll() is None

    def stop(self) -> None:
        self.stopped = True
        try:
            open(self.out + ".stop", "w").close()
        except OSError:
            pass
        end = time.time() + 10
        while self.alive and time.time() < end:
            time.sleep(0.05)
        if self.alive:
            self.proc.kill()

    def cleanup(self) -> None:
        for p in (self.out, self.out + ".tmp", self.out + ".stop"):
            try:
                os.remove(p)
            except OSError:
                pass


class DemoRun:
    SPEED = 25.0

    def __init__(self, pct: int, adapter: dict = None, vram_mb: int = 0, igpu: bool = False):
        self.adapter = dict(adapter or {})
        self.started = time.time()
        self.stopped = False
        total = vram_mb or 8192
        self.mb = plan_mb(int(total * 0.8), total, pct, igpu)
        self.n = len(patterns()) * 2 * (self.mb // 64)

    def poll(self) -> dict:
        if self.stopped:
            return {"state": "cancelled"}
        el = (time.time() - self.started) * self.SPEED
        done = min(self.n, int(el * 40))
        st = dict(kind="vram", mb=self.mb, target_mb=self.mb, done=done, total=self.n, errors=0, bad_bytes=0,
                  renderer=self.adapter.get("name") or "Demo GPU", vendor="", free_mb=int(self.mb * 1.6), oom=False,
                  pattern=patterns()[min(5, done * 6 // max(1, self.n))][0], t=round(el, 1))
        st["render_match"] = "match" if self.adapter.get("name") else ""
        st["state"] = "done" if done >= self.n else "running"
        return st

    @property
    def alive(self) -> bool:
        return self.poll().get("state") == "running"

    def stop(self) -> None:
        self.stopped = True

    def cleanup(self) -> None:
        pass


def start(pct: int, adapter: dict = None, vram_mb: int = 0, igpu: bool = False):
    if not E.IS_WIN:
        return DemoRun(pct, adapter, vram_mb, igpu)
    return Run(pct, adapter, vram_mb, igpu)


def vram_result(state: dict, adapter: dict) -> dict:
    import hwtests as HT
    st = state.get("state")
    f = []
    if st == "crash":
        f.append((HT.FAIL, "hwc.f.crash", dict(code=state.get("exit_code", "?"))))
    if state.get("errors"):
        f.append((HT.FAIL, "vt.f.errors", dict(n=state["errors"], b=state.get("bad_bytes", 0))))
    if state.get("render_match") == "other":
        f.append((HT.WARN, "vt.f.wrong_gpu", dict(got=state.get("renderer") or "?", want=(adapter or {}).get("name") or "?")))
    if state.get("oom"):
        f.append(("info", "vt.f.oom", dict(mb=state.get("mb", 0))))
    if (adapter or {}).get("kind") == "igpu":
        f.append(("info", "vt.f.igpu", {}))
    f.append(("info", "vt.f.partial", {}))
    status = HT.status_of(f)
    if st == "error":
        status = HT.NA
        f.append((HT.WARN, "hwc.f.error", dict(err=state.get("error", "?"))))
    if st == "cancelled" and status == HT.PASS:
        status = HT.SKIPPED
    rows = [("vt.r.gpu", state.get("renderer")), ("vt.r.tested", f"{state.get('mb', 0)} {tr('u.mb')}"),
            ("vt.r.free", f"{state['free_mb']} {tr('u.mb')}" if state.get("free_mb") else None),
            ("hwc.r.errors", state.get("errors", 0)), ("hwc.r.patterns", len(patterns())),
            ("hwc.r.duration", f"{int(state.get('t') or 0)} {tr('hwc.u.s')}")]
    return HT.result("vram", status, tr(f"vt.sum.{status}"), rows=rows, findings=f, mb=state.get("mb", 0),
                     errors=state.get("errors", 0), gpu=state.get("renderer"), log=state.get("log") or [])
