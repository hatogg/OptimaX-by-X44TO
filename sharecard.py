"""
OptimaX — картка результату для соцмереж: «мій ПК після OptimaX» з реальними замірами.

На картку потрапляє лише те, що справді виміряно на цьому ПК: FPS у грі до/після (PresentMon),
розумна оптимізація, бали GPU-тесту, час завантаження Windows, фонові процеси, пам'ять,
заблокована реклама, пінг. Якщо даних немає — плитки немає. Ім'я користувача й ПК не показуються.
"""
from __future__ import annotations

import re
import time

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap, QLinearGradient, QGuiApplication, QFont
from PyQt6.QtWidgets import QDialog, QLabel, QFileDialog

import engine as E
import features as F
from i18n import tr
from ui_kit import T, make_font, logo_pixmap, label, button, vbox, hbox, card, Switch, dark_titlebar

W, H = 1200, 675


def num(v) -> str:
    return f"{int(round(v)):,}".replace(",", " ")


def short_cpu(name: str) -> str:
    s = re.sub(r"\((R|TM|tm|r)\)", "", name or "")
    s = re.sub(r"\b(CPU|Processor|\d+-Core)\b", "", s)
    s = re.sub(r"@.*$", "", s)
    s = re.sub(r"\bwith Radeon.*$", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


def short_gpu(name: str) -> str:
    s = re.sub(r"\((R|TM|tm|r)\)", "", name or "")
    s = re.sub(r"^(NVIDIA|AMD|Intel)\s+", "", s.strip())
    return re.sub(r"\s+(Series|Graphics)$", "", s).strip()


def _pct(before, after):
    return (after - before) / before * 100 if before else 0.0


def hero_candidates() -> list:
    """Найкращі виміряні «до/після»: гра, розумна оптимізація, бали GPU-тесту."""
    out = []
    for exe, t in (F.CFG["fps_tests"] or {}).items():
        b, a = t.get("before"), t.get("after")
        if b and a and b.get("avg") and a.get("avg"):
            out.append(dict(kind="game", title=F.game_name(exe), before=b["avg"], after=a["avg"], unit="FPS",
                            pct=_pct(b["avg"], a["avg"]),
                            sub=tr("sc.low1", b=num(b.get("low1") or 0), a=num(a.get("low1") or 0))
                            if b.get("low1") and a.get("low1") else ""))
    sm = F.CFG["smart_last"] or {}
    if sm.get("base") and sm.get("final"):
        out.append(dict(kind="smart", title=tr("sc.hero_smart"), before=sm["base"]["avg"], after=sm["final"]["avg"],
                        unit="FPS", pct=_pct(sm["base"]["avg"], sm["final"]["avg"]),
                        sub=tr("sc.hero_smart_d", n=sm.get("measures", 0), r=len(sm.get("removed") or []))))
    hist = [h for h in (F.CFG["bench"] or []) if h.get("score") and h.get("kind", "own") == "own"]
    for preset in ("1080p", "1440p", "4k"):
        hs = [h for h in hist if h.get("preset") == preset]
        if len(hs) >= 2 and hs[-1]["score"] != hs[0]["score"]:
            out.append(dict(kind="bench", title=tr("sc.hero_bench", preset={"4k": "4K"}.get(preset, preset)),
                            before=hs[0]["score"], after=hs[-1]["score"], unit=tr("gb.points"),
                            pct=_pct(hs[0]["score"], hs[-1]["score"]), sub=""))
    order = {"game": 0, "smart": 1, "bench": 2}
    return sorted(out, key=lambda h: (h["pct"] <= 0, order[h["kind"]], -h["pct"]))


METRICS = [("boot_ms", "sc.t.boot", True), ("processes", "sc.t.processes", True),
           ("ram_used_gb", "sc.t.ram", True), ("services", "sc.t.services", True)]


def _fmt(key: str, v) -> str:
    if key == "boot_ms":
        return tr("u.sec", v=f"{v / 1000:.0f}")
    if key == "ram_used_gb":
        return tr("u.gb", v=f"{v:.1f}")
    return num(v)


def collect(main, show_hw: bool = True) -> dict:
    hw = main.hw or {}
    d = dict(when=time.strftime("%d.%m.%Y"), tweaks=E.JOURNAL.count(), hw_line="", hero=None, tiles=[])
    if show_hw:
        parts = [short_cpu(hw.get("cpu", ""))]
        if hw.get("gpus"):
            parts.append(short_gpu(hw["gpus"][0][0]))
        if hw.get("ram_gb"):
            parts.append(tr("u.gb", v=int(round(hw["ram_gb"]))))
        d["hw_line"] = " · ".join(p for p in parts if p)
    heroes = hero_candidates()
    d["hero"] = heroes[0] if heroes else None
    before = F.CFG["snapshot"] or {}
    now = getattr(main.pages.get("home"), "metrics", None) or {}
    for key, cap, lower_better in METRICS:
        b, n = before.get(key), now.get(key)
        if b and n is not None and abs(_pct(b, n)) >= 1:
            pct = _pct(b, n)
            d["tiles"].append(dict(title=tr(cap), value=f"{_fmt(key, b)} → {_fmt(key, n)}", pct=pct,
                                   good=(pct < 0) if lower_better else (pct > 0)))
    try:
        import adblock as AB
        sn = AB.Backend(F.CFG).stats()
        if sn and sn.get("today", {}).get("blocked"):
            d["tiles"].append(dict(title=tr("sc.t.ads"), value=num(sn["today"]["blocked"]),
                                   sub=tr("sc.t.ads_d", pct=sn.get("pct", 0))))
    except Exception:
        pass
    ping = [r for r in ((F.CFG["net"] or {}).get("ping") or []) if r.get("avg") and not r.get("baseline")]
    if ping:
        best = min(ping, key=lambda r: r["avg"])
        name = best.get("name") or tr(f"net.r.{best.get('code')}")
        d["tiles"].append(dict(title=tr("sc.t.ping", name=name), value=tr("u.ms", v=f"{best['avg']:.0f}"),
                               sub=tr("sc.t.ping_d", j=f"{best.get('jitter') or 0:.0f}")))
    if len(d["tiles"]) < 4 and d["tweaks"]:
        d["tiles"].append(dict(title=tr("sc.t.tweaks"), value=num(d["tweaks"]), sub=tr("sc.t.tweaks_d")))
    d["tiles"] = d["tiles"][:4]
    return d


# ───────────────────────── малювання ─────────────────────────
def _text(p, rect, text, px, color, weight=QFont.Weight.Normal, align=None):
    p.setFont(make_font(px, weight))
    p.setPen(QColor(color))
    p.drawText(QRectF(*rect), align if align is not None else (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
               text)


PREVIEW = (600, 338)


def preview_pixmap(d: dict, screen_dpr: float = 1.0) -> QPixmap:
    """Зменшена копія картки для вікна: рівно 600×338 на екрані й чітка на екранах 125–200%.
    (Картка має логічний розмір 1200×675 за будь-якого DPR, тож її треба саме зменшити, а не лише змінити DPR.)"""
    pm = render(d, 2.0 * screen_dpr)
    small = pm.scaled(round(PREVIEW[0] * screen_dpr), round(PREVIEW[1] * screen_dpr),
                      Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    small.setDevicePixelRatio(screen_dpr)
    return small


def render(d: dict, dpr: float = 2.0) -> QPixmap:
    pm = QPixmap(int(W * dpr), int(H * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bg = QLinearGradient(0, 0, W, H)
    bg.setColorAt(0, QColor("#0B0E17"))
    bg.setColorAt(1, QColor("#171230"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(0, 0, W, H), 1, 1)
    for (x, y, r), col, a in (((W - 110, 70, 300), T["acc"], 30), ((150, H + 80, 360), T["acc2"], 26)):
        c = QColor(col)
        c.setAlpha(a)
        p.setBrush(c)
        p.drawEllipse(QPointF(x, y), r, r)

    # шапка
    p.drawPixmap(QPointF(64, 50), logo_pixmap(52))
    _text(p, (130, 50, 400, 30), "OptimaX", 26, T["text"], QFont.Weight.Bold)
    _text(p, (130, 82, 400, 22), "by X44TO", 15, T["sub"])
    _text(p, (W - 364, 54, 300, 24), d.get("when", ""), 15, T["sub"], align=Qt.AlignmentFlag.AlignRight |
          Qt.AlignmentFlag.AlignVCenter)
    _text(p, (64, 140, W - 128, 54), tr("sc.title"), 40, T["text"], QFont.Weight.Bold)
    if d.get("hw_line"):
        _text(p, (64, 196, W - 128, 28), d["hw_line"], 18, T["sub"])

    # головний показник
    hero = d.get("hero")
    box = QRectF(64, 248, W - 128, 190)
    panel = QColor(T["surf"])
    panel.setAlpha(225)
    p.setBrush(panel)
    p.setPen(QPen(QColor(T["acc_line"]), 1.2))
    p.drawRoundedRect(box, 24, 24)
    if hero:
        _text(p, (100, 268, 760, 26), hero["title"], 18, T["sub"])
        val = lambda v: num(v)  # noqa: E731
        _text(p, (100, 300, 250, 84), val(hero["before"]), 46, T["mute"], QFont.Weight.DemiBold,
              Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        _text(p, (356, 300, 70, 84), "→", 40, T["sub"], align=Qt.AlignmentFlag.AlignCenter)
        _text(p, (432, 300, 300, 84), val(hero["after"]), 66, T["text"], QFont.Weight.Bold)
        _text(p, (100, 386, 760, 26), (hero["unit"] + ("   ·   " + hero["sub"] if hero.get("sub") else "")), 16,
              T["sub"])
        good = hero["pct"] >= 0
        bx = (W - 64 - 36 - 250, 290, 250, 110)
        fill = QColor(T["ok_bg"] if good else T["bad_bg"])
        p.setBrush(fill)
        p.setPen(QPen(QColor(T["ok_line"] if good else T["bad_line"]), 1.2))
        p.drawRoundedRect(QRectF(*bx), 22, 22)
        _text(p, bx, f"{hero['pct']:+.0f}%", 58, T["ok"] if good else T["bad"], QFont.Weight.Bold,
              Qt.AlignmentFlag.AlignCenter)
    else:
        _text(p, (100, 280, W - 200, 60), tr("sc.no_hero_t", n=d.get("tweaks", 0)), 34, T["text"], QFont.Weight.Bold)
        _text(p, (100, 346, W - 200, 60), tr("sc.no_hero_d"), 17, T["sub"])

    # плитки
    tiles = d.get("tiles") or []
    if tiles:
        gap = 16
        tw = (W - 128 - gap * (len(tiles) - 1)) / len(tiles)
        for i, t in enumerate(tiles):
            x, y = 64 + i * (tw + gap), 462
            c = QColor(T["surf"])
            c.setAlpha(215)
            p.setBrush(c)
            p.setPen(QPen(QColor(T["line2"]), 1))
            p.drawRoundedRect(QRectF(x, y, tw, 142), 18, 18)
            _text(p, (x + 20, y + 16, tw - 40, 22), t["title"], 15, T["sub"])
            _text(p, (x + 20, y + 44, tw - 40, 44), t["value"], 27 if "→" in t["value"] else 32, T["text"],
                  QFont.Weight.Bold)
            if "pct" in t:
                _text(p, (x + 20, y + 96, tw - 40, 26), f"{t['pct']:+.0f}%", 18,
                      T["ok"] if t["good"] else T["bad"], QFont.Weight.DemiBold)
            elif t.get("sub"):
                _text(p, (x + 20, y + 96, tw - 40, 26), t["sub"], 15, T["sub"])

    # підвал
    _text(p, (64, 622, W - 420, 26), tr("sc.footer"), 14, T["mute"])
    _text(p, (W - 364, 622, 300, 26), f"OptimaX {E.VERSION} · X44TO", 14, T["mute"],
          align=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    p.end()
    return pm


# ───────────────────────── вікно «Поділитися» ─────────────────────────
class ShareDialog(QDialog):
    def __init__(self, main):
        super().__init__(main)
        self.main = main
        self.setWindowTitle(f"{E.APP_TITLE} — {tr('sc.title_dlg')}")
        self.setModal(True)
        self.show_hw = True
        v = vbox(self, (24, 22, 24, 20), 12)
        v.addWidget(label(tr("sc.title_dlg"), "h2"))
        v.addWidget(label(tr("sc.sub"), "desc", wrap=True))
        frame = card()
        fv = vbox(frame, (12, 12, 12, 12))
        self.preview = QLabel()
        self.preview.setFixedSize(600, 338)
        fv.addWidget(self.preview)
        v.addWidget(frame, 0, Qt.AlignmentFlag.AlignHCenter)
        hw = hbox(spacing=10)
        self.sw_hw = Switch()
        self.sw_hw.set_quiet(True)
        self.sw_hw.toggled.connect(self._toggle_hw)
        hw.addWidget(self.sw_hw)
        hw.addWidget(label(tr("sc.show_hw"), "desc"), 1)
        v.addLayout(hw)
        bh = hbox(spacing=8)
        bh.addStretch()
        bh.addWidget(button(tr("sc.copy"), None, self.copy))
        bh.addWidget(button(tr("sc.save"), "primary", self.save))
        bh.addWidget(button(tr("btn.close"), None, self.accept))
        v.addLayout(bh)
        self.refresh()

    def showEvent(self, e):
        dark_titlebar(self)
        super().showEvent(e)

    def _toggle_hw(self, on: bool):
        self.show_hw = on
        self.refresh()

    def refresh(self):
        self.data = collect(self.main, self.show_hw)
        self.preview.setPixmap(preview_pixmap(self.data, self._screen_dpr()))

    def _screen_dpr(self) -> float:
        try:
            return max(1.0, float(self.devicePixelRatioF() or 1.0))
        except (TypeError, ValueError):
            return 1.0

    def save(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("sc.save"), f"OptimaX-{time.strftime('%Y-%m-%d')}.png",
                                              "PNG (*.png)")
        if not path:
            return
        if render(self.data, 2.0).save(path, "PNG"):
            self.main.toast(tr("sc.saved"))
        else:
            self.main.toast(tr("sc.save_fail"), "bad")

    def copy(self):
        QGuiApplication.clipboard().setPixmap(render(self.data, 2.0))
        self.main.toast(tr("sc.copied"))
