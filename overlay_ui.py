"""
OptimaX — вікно FPS-оверлея і його керування (Qt). Логіка кадрів, визначення гри й звіт сесії — overlay.py.

OverlayController живе, поки працює програма: раз на 250 мс дивиться, яке вікно на передньому плані; якщо це гра —
запускає PresentMon для її процесу, датчики раз на секунду, показує оверлей на моніторі гри; гра закрилася чи пішла
з переднього плану — ховає. Гарячі клавіші — окремий набір (hotkeys.Listener з власною таблицею): показати/сховати і
почати/зупинити запис сесії.
"""
from __future__ import annotations

import ctypes
import time

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF, QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QFont, QGuiApplication
from PyQt6.QtWidgets import QWidget

import engine as E
import features as F
import overlay as OV
from i18n import tr
from ui_kit import LOG

COLORS = {"main": QColor("#FFFFFF"), "dim": QColor("#C9D1E3"), "warn": QColor("#FFC24D")}
WS_EX = 0x00080000 | 0x00000020 | 0x00000008 | 0x00000080 | 0x08000000  # LAYERED|TRANSPARENT|TOPMOST|TOOLWINDOW|NOACTIVATE


class OverlayWindow(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.lines = []
        self.graph = []
        self.rec = False
        self.scale = 1.0
        self.opacity = 0.85
        self.styled = False

    def apply_styles(self) -> None:
        """Стилі Windows поверх прапорців Qt: пропускати кліки, не активуватися, не бути в Alt+Tab."""
        if not E.IS_WIN or self.styled:
            return
        try:
            u = ctypes.windll.user32
            hwnd = int(self.winId())
            get, set_ = u.GetWindowLongPtrW, u.SetWindowLongPtrW
            get.restype, get.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int]
            set_.restype, set_.argtypes = ctypes.c_ssize_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            set_(hwnd, -20, get(hwnd, -20) | WS_EX)  # GWL_EXSTYLE
            self.styled = True
        except Exception:
            pass

    def keep_on_top(self) -> None:
        if not E.IS_WIN:
            return
        try:
            u = ctypes.windll.user32
            u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 4 + [ctypes.c_uint]
            # HWND_TOPMOST, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            u.SetWindowPos(int(self.winId()), ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0010)
        except Exception:
            pass

    def set_content(self, lines: list, graph: list, rec: bool) -> None:
        self.lines, self.graph, self.rec = lines, graph, rec
        fm_h = int(19 * self.scale)
        w = int(250 * self.scale)
        h = int(12 * self.scale) * 2 + fm_h * len(lines) + (int(46 * self.scale) if graph else 0)
        if (self.width(), self.height()) != (w, h):
            self.resize(w, h)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(8, 10, 18, int(200 * self.opacity)))
        p.drawRoundedRect(r, 9 * self.scale, 9 * self.scale)
        pad = 10 * self.scale
        y = pad
        for i, (text, kind) in enumerate(self.lines):
            f = QFont("Segoe UI")
            f.setPixelSize(int((17 if i == 0 else 12) * self.scale))
            if i == 0:
                f.setWeight(QFont.Weight.Bold)
            p.setFont(f)
            p.setPen(COLORS.get(kind, COLORS["dim"]))
            h = 19 * self.scale
            p.drawText(QRectF(pad, y, r.width() - 2 * pad, h), int(Qt.AlignmentFlag.AlignVCenter), text)
            y += h
        if self.rec:
            p.setBrush(QColor("#FF4D5E"))
            p.drawEllipse(QPointF(r.width() - pad - 4, pad + 9 * self.scale), 4 * self.scale, 4 * self.scale)
        if self.graph:
            gh = 38 * self.scale
            gr = QRectF(pad, y + 4 * self.scale, r.width() - 2 * pad, gh)
            vals = self.graph
            hi = max(max(vals), 1.0)
            path = QPainterPath()
            for i, v in enumerate(vals):
                pt = QPointF(gr.left() + gr.width() * i / max(1, len(vals) - 1), gr.bottom() - gr.height() * v / hi)
                path.moveTo(pt) if i == 0 else path.lineTo(pt)
            p.setPen(QPen(QColor("#7AA2FF"), 1.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.end()


class OverlayController(QObject):
    hotkey = pyqtSignal(str)
    notify = pyqtSignal(str, str)

    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.win = None
        self.stream = None
        self.game = {}
        self.sensors = None
        self.last_s = {}
        self.next_sensor = 0.0
        self.seen_since = 0.0
        self.mode_before = ""
        self.flip_warned = set()
        self.excl_warned = set()
        self.rec = None  # {t0, frames, samples, recorder}
        self.gpu_name = ""
        self.cpu_state = None
        self.cpu_self = None
        self.hk = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.hotkey.connect(self._hotkey)
        self.notify.connect(lambda text, kind: self.main.toast(text, kind))
        self.known = set()
        self.known_ts = 0.0

    @property
    def cfg(self) -> dict:
        return dict(F.CFG["overlay"] or {})

    def set_enabled(self, on: bool) -> list:
        c = self.cfg
        c["enabled"] = on
        F.CFG["overlay"] = c
        if on:
            self.timer.start(OV.UPDATE_MS)
            return self.start_hotkeys()
        self.timer.stop()
        self.hide()
        self.stop_hotkeys()
        return []

    def start(self) -> None:
        if self.cfg.get("enabled"):
            self.set_enabled(True)

    # ── гарячі клавіші ──
    def hotkey_table(self) -> dict:
        i = int(self.cfg.get("hotkey") or 0) % len(OV.HOTKEY_PRESETS)
        t1, m1, v1, t2, m2, v2 = OV.HOTKEY_PRESETS[i]
        return {11: ("overlay", m1, v1, t1), 12: ("overlay_rec", m2, v2, t2)}

    def start_hotkeys(self) -> list:
        import hotkeys as HK
        self.stop_hotkeys()
        self.hk = HK.Listener(self.hotkey.emit, self.hotkey_table())
        busy = self.hk.start()
        if busy:
            self.notify.emit(tr("ov.hk_busy", keys=", ".join(t for a, _m, _v, t in self.hotkey_table().values()
                                                               if a in busy)), "warn")
        return busy

    def stop_hotkeys(self) -> None:
        if self.hk:
            self.hk.stop()
            self.hk = None

    def _hotkey(self, action: str) -> None:
        if action == "overlay":
            c = self.cfg
            c["hidden"] = not c.get("hidden")
            F.CFG["overlay"] = c
            if c["hidden"]:
                self.hide(keep_stream=True)
        elif action == "overlay_rec":
            self.toggle_record()

    # ── цикл ──
    def tick(self) -> None:
        c = self.cfg
        if time.time() - self.known_ts > 60:
            self.known, self.known_ts = OV.known_games(), time.time()
        fg = OV.foreground() if E.IS_WIN else (self.game or {})
        game = fg if fg and OV.is_game(fg, self.known, c) else {}
        if not game:
            if self.game and (not fg or fg.get("pid") != self.game.get("pid")):
                if self.rec and not (self.stream and self.stream.alive):
                    self.toggle_record()
                self.hide(keep_stream=bool(self.rec))
            return
        if game.get("pid") != self.game.get("pid"):
            self.switch(game)
        if time.time() >= self.next_sensor:
            self.next_sensor = time.time() + OV.SENSOR_S
            self.last_s = self.sensors.sample(1.0) if self.sensors else {}
            if self.rec is not None:
                self.rec["samples"].append(dict(self.last_s, t=round(time.time() - self.rec["t0"], 1)))
                if self.rec.get("recorder"):
                    self.rec["recorder"].sample()
            pct, self.cpu_state = OV.self_cpu_percent(self.cpu_state)
            if pct is not None:
                self.cpu_self = pct
        st = self.stream.stats() if self.stream else {}
        mode = self.stream.mode if self.stream else ""
        if not self.win or not self.win.isVisible():
            if mode and not self.mode_before:
                self.mode_before = mode
            if time.time() - self.seen_since < OV.SHOW_DELAY_S or c.get("hidden"):
                return
            self.show_on(game)
        elif self.mode_before and mode and OV.flip_downgrade(self.mode_before, mode) and \
                game["exe"] not in self.flip_warned:
            self.flip_warned.add(game["exe"])
            self.notify.emit(tr("ov.flip", game=game["exe"]), "warn")
        if mode and OV.is_exclusive(mode) and game["exe"] not in self.excl_warned:
            self.excl_warned.add(game["exe"])
            self.notify.emit(tr("ov.exclusive", game=game["exe"]), "warn")
        if not self.gpu_name and E.IS_WIN and time.time() - self.seen_since > 8:
            self.gpu_name = OV.render_gpu(game["pid"]) or " "
        lines = OV.overlay_lines(c.get("mode", "standard"), st, self.last_s, dict(gpu=self.gpu_name.strip(), mode=mode))
        graph = self.stream.series(160) if (self.stream and c.get("mode") == "extended") else []
        self.win.set_content(lines, graph, self.rec is not None)
        self.win.keep_on_top()

    def switch(self, game: dict) -> None:
        self.hide()
        self.game = game
        self.seen_since = time.time()
        self.mode_before = ""
        self.gpu_name = ""
        import fpstest as FT
        import hwtests as HT
        pm = FT.find_presentmon() if E.IS_WIN else ""
        try:
            self.stream = OV.Stream(pm, game["pid"]) if pm else (OV.DemoStream() if not E.IS_WIN else None)
        except OSError as e:
            LOG.write(tr("e.err", err=e))
            self.stream = None
        if E.IS_WIN and not pm and "pm" not in self.excl_warned:
            self.excl_warned.add("pm")
            self.notify.emit(tr("ov.no_pm"), "warn")
        self.sensors = HT.Sensors(self.main.hw or {}, gpu=True)

    def show_on(self, game: dict) -> None:
        c = self.cfg
        if self.win is None:
            self.win = OverlayWindow()
        self.win.scale = max(0.6, min(2.0, (c.get("size") or 100) / 100))
        self.win.opacity = max(0.2, min(1.0, (c.get("opacity") or 85) / 100))
        self.win.set_content(OV.overlay_lines(c.get("mode", "standard"), {}, {}, {}), [], False)
        geo = self._screen_geo(game.get("monitor"))
        margin = int(14 * self.win.scale)
        corner = c.get("corner", "tl")
        x = geo.left() + margin if corner in ("tl", "bl") else geo.right() - self.win.width() - margin
        y = geo.top() + margin if corner in ("tl", "tr") else geo.bottom() - self.win.height() - margin
        self.win.move(x, y)
        self.win.show()
        self.win.apply_styles()

    @staticmethod
    def _screen_geo(mon):
        screens = QGuiApplication.screens()
        if mon:
            cx, cy = (mon[0] + mon[2]) // 2, (mon[1] + mon[3]) // 2
            for s in screens:
                g = s.geometry()
                dpr = s.devicePixelRatio()
                if g.left() <= cx < g.left() + g.width() * dpr and g.top() <= cy < g.top() + g.height() * dpr:
                    return g
        return (QGuiApplication.primaryScreen() or screens[0]).geometry()

    def hide(self, keep_stream: bool = False) -> None:
        if self.win:
            self.win.hide()
        if not keep_stream:
            if self.stream:
                self.stream.stop()
            self.stream = None
            if self.sensors:
                self.sensors.close()
            self.sensors = None
            self.game = {}

    # ── запис сесії ──
    def toggle_record(self) -> None:
        import procmon as PM
        if self.rec is None:
            if not self.stream:
                self.notify.emit(tr("ov.rec_no_game"), "warn")
                return
            self.rec = dict(t0=time.time(), samples=[], game=self.game.get("exe", ""),
                            recorder=PM.Recorder(self.game.get("exe", ""), manual=True))
            self.stream.recording = []
            self.notify.emit(tr("ov.rec_on"), "ok")
            return
        rec, self.rec = self.rec, None
        frames = list(self.stream.recording or []) if self.stream else []
        if self.stream:
            self.stream.recording = None
        procs = rec["recorder"].finish(None) if rec.get("recorder") else {}
        if len(frames) < 30:
            self.notify.emit(tr("ov.rec_short"), "warn")
            return
        try:
            rep = OV.session_report(frames, rec["samples"], rec["game"], rec["t0"], procs)
            path = OV.save_session(rep, frames)
            sess = list(F.CFG["overlay_sessions"] or [])
            sess.append(dict(path=path, game=rec["game"], ts=int(rec["t0"]), stats=rep["stats"],
                             diag=[d["key"] for d in rep["diag"]]))
            F.CFG["overlay_sessions"] = sess[-30:]
            PM.save_session(F.CFG, procs)
            self.notify.emit(tr("ov.rec_saved", fps=rep["stats"].get("avg", 0), low=rep["stats"].get("low1", 0)), "ok")
        except Exception as e:  # noqa: BLE001
            LOG.write(tr("e.err", err=f"{type(e).__name__}: {e}"))

    def shutdown(self) -> None:
        self.timer.stop()
        self.hide()
        self.stop_hotkeys()
