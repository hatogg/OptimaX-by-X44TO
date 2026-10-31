"""
OptimaX — сторінка «Бібліотека»: ігри з обкладинками, запуск, час гри й історія FPS (логіка — library.py).
"""
from __future__ import annotations

import os
from datetime import datetime

from PyQt6.QtCore import Qt, QRectF, QFileInfo, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap, QLinearGradient, QFont
from PyQt6.QtWidgets import QWidget, QFrame, QLabel, QGridLayout, QFileIconProvider

import engine as E
import fpstest as FT
import library as LB
from i18n import tr
from ui_kit import T, label, button, card, vbox, hbox, badge, scroller, page_header, Switch, Spark, Ask, make_font

TILE_W, TILE_H = 150, 225
_COVERS: dict = {}


def placeholder(g: dict, w: int, h: int) -> QPixmap:
    """Обкладинки немає: градієнт, іконка exe і назва гри."""
    pm = QPixmap(w * 2, h * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    hue = sum(map(ord, g["name"])) % 360
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor.fromHsl(hue, 90, 70))
    grad.setColorAt(1, QColor.fromHsl((hue + 40) % 360, 80, 28))
    p.setBrush(grad)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, w, h), 10, 10)
    main = g.get("main") or ""
    if main and os.path.isfile(main):
        ic = QFileIconProvider().icon(QFileInfo(main)).pixmap(48, 48)
        if not ic.isNull():
            p.drawPixmap(int(w / 2 - 24), int(h * 0.30), ic)
    p.setPen(QColor("#FFFFFF"))
    f = make_font(14, QFont.Weight.DemiBold)
    p.setFont(f)
    flags = (Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop).value | Qt.TextFlag.TextWordWrap.value
    p.drawText(QRectF(10, h * 0.55, w - 20, h * 0.4), flags, g["name"])
    p.end()
    return pm


def cover_pixmap(g: dict, w: int = TILE_W, h: int = TILE_H) -> QPixmap:
    key = (g["key"], w, h)
    if key in _COVERS:
        return _COVERS[key]
    path = LB.cover(g) if E.IS_WIN else ""
    pm = QPixmap(path) if path else QPixmap()
    if pm.isNull():
        out = placeholder(g, w, h)
    else:
        scaled = pm.scaled(w * 2, h * 2, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
        x, y = (scaled.width() - w * 2) // 2, (scaled.height() - h * 2) // 2
        out = scaled.copy(x, y, w * 2, h * 2)
        out.setDevicePixelRatio(2)
    _COVERS[key] = out
    return out


class GameTile(QFrame):
    clicked = pyqtSignal(object)

    def __init__(self, g: dict):
        super().__init__()
        self.g = g
        self.setObjectName("row")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(TILE_W + 16)
        v = vbox(self, (8, 8, 8, 8), 4)
        self.img = QLabel()
        self.img.setFixedSize(TILE_W, TILE_H)
        self.img.setPixmap(cover_pixmap(g))
        v.addWidget(self.img)
        name = label(g["name"], "rowTitle")
        name.setFixedWidth(TILE_W)
        name.setToolTip(g["name"])
        v.addWidget(name)
        self.sub = label("", "muted")
        v.addWidget(self.sub)
        self.sync()

    def sync(self):
        t = LB.play_time(self.g["exes"])
        fps = LB.fps_history(self.g["exes"])
        parts = [LB.fmt_hours(t)] if t else []
        if fps and fps[-1].get("avg"):
            parts.append(f"{fps[-1]['avg']:.0f} FPS")
        self.sub.setText(" · ".join(parts) or tr(f"mg.store.{self.g['store']}"))

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.g)
        super().mouseReleaseEvent(e)


class LibraryPage(QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self.tiles = []
        self.sel = None
        outer = vbox(self)
        right = QWidget()
        rh = hbox(right, spacing=10)
        self.btn_refresh = button(tr("lib.refresh"), "ghost", self.refresh)
        rh.addWidget(self.btn_refresh)
        outer.addWidget(page_header(tr("nav.library"), tr("lib.sub"), right))
        body = QWidget()
        v = vbox(body, (32, 4, 32, 24), 14)

        # обрана гра
        self.det = card("cardAccent")
        dh = hbox(self.det, (20, 18, 20, 18), 18)
        self.det_img = QLabel()
        self.det_img.setFixedSize(170, 255)
        dh.addWidget(self.det_img, 0, Qt.AlignmentFlag.AlignTop)
        dv = vbox(spacing=6)
        top = hbox(spacing=8)
        self.det_name = label("", "h1", wrap=True)
        top.addWidget(self.det_name, 1)
        self.det_store = badge("", "muted")
        top.addWidget(self.det_store, 0, Qt.AlignmentFlag.AlignTop)
        dv.addLayout(top)
        self.det_info = label("", "desc", wrap=True)
        dv.addWidget(self.det_info)
        bh = hbox(spacing=8)
        self.btn_play = button(tr("lib.play"), "primary", self.play)
        self.btn_play.setMinimumWidth(140)
        bh.addWidget(self.btn_play)
        self.btn_folder = button(tr("lib.folder"), "ghost", self.open_folder)
        bh.addWidget(self.btn_folder)
        self.btn_mining = button(tr("lib.mining"), "ghost", self.open_mining)
        bh.addWidget(self.btn_mining)
        bh.addStretch()
        dv.addLayout(bh)
        self.det_mining = label("", "desc", wrap=True)
        dv.addWidget(self.det_mining)
        dv.addWidget(label(tr("lib.fps_title"), "h3"))
        self.chart = Spark(110, "FPS")
        dv.addWidget(self.chart)
        self.det_fps = label("", "desc", wrap=True)
        dv.addWidget(self.det_fps)
        dv.addStretch()
        dh.addLayout(dv, 1)
        self.det.hide()
        v.addWidget(self.det)

        # налаштування
        opts = card()
        ov = vbox(opts, (20, 14, 20, 14), 8)
        for key, default in (("boost", True), ("fps", True)):
            r = hbox(spacing=12)
            sw = Switch()
            sw.set_quiet(bool(LB.setting(key, default)))
            sw.clicked.connect(lambda on, k=key: self._set(k, on))
            r.addWidget(sw, 0, Qt.AlignmentFlag.AlignTop)
            tv = vbox(spacing=1)
            tv.addWidget(label(tr(f"lib.opt.{key}"), "rowTitle"))
            tv.addWidget(label(tr(f"lib.opt.{key}.d"), "desc", wrap=True))
            r.addLayout(tv, 1)
            ov.addLayout(r)
            setattr(self, f"sw_{key}", sw)
        pr = hbox(spacing=10)
        self.pm_state = label("", "desc", wrap=True)
        pr.addWidget(self.pm_state, 1)
        self.btn_pm = button(tr("fps.get_pm"), None, self.get_pm)
        pr.addWidget(self.btn_pm)
        ov.addLayout(pr)
        v.addWidget(opts)

        # плитки
        self.empty = label(tr("lib.empty"), "sub", wrap=True)
        v.addWidget(self.empty)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        gw = QWidget()
        gw.setLayout(self.grid)
        v.addWidget(gw)
        v.addStretch()
        outer.addWidget(scroller(body), 1)
        self.cols = 5
        self.sync_pm()
        self.show_games(LB.games())
        if not LB.games() or LB.due():
            self.refresh(silent=True)

    # ── список ──
    def refresh(self, silent: bool = False):
        self.main.run_quick(tr("nav.library"), lambda log, p: {"games": LB.refresh()}, silent=True,
                            busy=None if silent else self.btn_refresh,
                            on_done=lambda r: self.show_games((r or {}).get("games") if isinstance(r, dict) else None))

    def order(self, games: list) -> list:
        return sorted(games, key=lambda g: (-LB.last_played(g["exes"]), g["name"].lower()))

    def show_games(self, games):
        if games is None:
            return
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.tiles = []
        for i, g in enumerate(self.order(games)):
            t = GameTile(g)
            t.clicked.connect(self.select)
            self.grid.addWidget(t, i // self.cols, i % self.cols, Qt.AlignmentFlag.AlignTop)
            self.tiles.append(t)
        self.grid.setColumnStretch(self.cols, 1)
        self.empty.setVisible(not games)
        if self.sel:
            g = next((x for x in games if x["key"] == self.sel["key"]), None)
            if g:
                self.select(g)

    def resizeEvent(self, e):
        cols = max(2, (self.width() - 90) // (TILE_W + 28))
        if cols != self.cols and self.tiles:
            self.cols = cols
            for i, t in enumerate(self.tiles):
                self.grid.addWidget(t, i // cols, i % cols, Qt.AlignmentFlag.AlignTop)
        else:
            self.cols = cols
        super().resizeEvent(e)

    def on_show(self):
        for t in self.tiles:
            t.sync()
        self.sync_pm()
        if self.sel:
            self.select(self.sel)

    # ── обрана гра ──
    def select(self, g: dict):
        self.sel = g
        self.det.show()
        self.det_img.setPixmap(cover_pixmap(g, 170, 255))
        self.det_name.setText(g["name"])
        self.det_store.setText(tr(f"mg.store.{g['store']}"))
        t = LB.play_time(g["exes"])
        last = LB.last_played(g["exes"])
        n = sum(1 for s in LB.sessions() if s.get("exe") in g["exes"])
        info = [tr("lib.time", t=LB.fmt_hours(t)) if t else tr("lib.never")]
        if last:
            info.append(tr("lib.last", when=datetime.fromtimestamp(last).strftime("%d.%m.%Y %H:%M")))
        if n:
            info.append(tr("lib.sessions", n=n))
        if g.get("anticheat"):
            info.append(tr("lib.anticheat", name=g["anticheat"]))
        self.det_info.setText(" · ".join(info))
        self.btn_play.setEnabled(bool(LB.launch_target(g)))
        hist = LB.fps_history(g["exes"])
        self.chart.set_series([([r["avg"] for r in hist if r.get("avg")], T["acc"]),
                               ([r["low1"] for r in hist if r.get("low1")], T["warn"])])
        if hist:
            r = hist[-1]
            self.det_fps.setText(tr("lib.fps_last", avg=f"{r.get('avg') or 0:.0f}", low=f"{r.get('low1') or 0:.0f}",
                                    st=f"{r.get('stutters_pm') or 0:.1f}", n=len(hist),
                                    when=datetime.fromtimestamp(r["ts"]).strftime("%d.%m %H:%M")))
        else:
            self.det_fps.setText(tr("lib.fps_none") if FT.find_presentmon() else tr("lib.fps_need_pm"))
        mining = self.main.hw and self.main.hw.get("mining_gpu")
        self.btn_mining.setVisible(bool(mining))
        self.det_mining.setVisible(bool(mining))
        if mining:
            import gamedb as DB
            import mining as MG
            mg = next((x for x in (self.main.pages["games"].mining.games if self.main.pages["games"].mining else [])
                       if MG.game_key(x) == g["key"]), None)
            if mg:
                last_chk = DB.verified(mg)
                text = tr("lib.mode", mode=tr(f"mg.mode.{MG.current_mode(mg)}"))
                if last_chk.get("verdict") in ("mining", "igpu", "warp"):
                    text += " · " + tr(f"diag.render.{last_chk['verdict']}")
                self.det_mining.setText(text)
            else:
                self.det_mining.setText("")

    def play(self):
        g = self.sel
        if not g:
            return
        self.main.launch_game(g, self.btn_play)

    def open_folder(self):
        if self.sel and E.IS_WIN and not E.DRY_RUN:
            os.startfile(self.sel["dir"])  # noqa: лише Windows

    def open_mining(self):
        if not self.sel:
            return
        self.main.go("games")
        card_ = self.main.pages["games"].mining
        row = next((r for r in (card_.rows if card_ else []) if r.g["dir"].lower().rstrip("\\/") == self.sel["key"]),
                   None)
        if row:
            card_.mode_menu(row)

    # ── налаштування ──
    def _set(self, key: str, on: bool):
        LB.set_setting(key, on)
        if key == "fps" and on and not FT.find_presentmon():
            self.main.toast(tr("lib.fps_need_pm"), "warn")

    def sync_pm(self):
        pm = FT.find_presentmon()
        self.pm_state.setText(tr("fps.pm_ok") if pm else tr("fps.pm_missing"))
        self.btn_pm.setVisible(not pm)

    def get_pm(self):
        if not Ask.ask(self, tr("fps.get_pm"), tr("fps.get_pm_q"), tr("fps.download")):
            return
        self.main.run_quick("PresentMon", lambda log, p: FT.download_presentmon(log), busy=self.btn_pm, silent=True,
                            on_done=lambda _r: self.sync_pm())
