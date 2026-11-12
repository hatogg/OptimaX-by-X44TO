"""
OptimaX — набір інтерфейсу: тема, іконки, перемикачі, картки, діалоги, консоль виконання.
"""
from __future__ import annotations

import ctypes
import html
import os
import sys

import re

from PyQt6.QtCore import (Qt, QThread, pyqtSignal, pyqtProperty, QTimer, QPropertyAnimation, QEasingCurve,
                          QRectF, QPointF, QSize, QObject, QRect, QPoint)
from PyQt6.QtGui import (QColor, QPainter, QPen, QIcon, QPixmap, QPainterPath, QFont, QLinearGradient, QPalette)
from PyQt6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QAbstractButton, QHBoxLayout, QVBoxLayout,
                             QScrollArea, QPlainTextEdit, QProgressBar, QDialog, QGraphicsOpacityEffect, QSizePolicy,
                             QLayout)

import engine as E
from i18n import tr

FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)


def asset(name: str):
    for d in (APP_DIR, BUNDLE_DIR):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return None


# ───────────────────────── тема ─────────────────────────
# Дві палітри з однаковими ключами. Кожен колір унікальний у межах обох палітр (і не #FFFFFF / #000000): так
# перемикання теми наживо може перефарбувати навіть рядки стилів, де колір уже підставлено (remap_hex).
THEMES = {
    "dark": {
        "bg": "#060A13", "side": "#090E1A", "surf": "#0E1524", "surf2": "#131C2F", "hover": "#1A2440",
        "line": "#19223A", "line2": "#243052", "line3": "#33416A",
        "text": "#E9EFFA", "sub": "#93A0BA", "mute": "#5D6984",
        "acc": "#3B82FF", "acc_h": "#6AA1FF", "acc2": "#8B5CF6", "acc2_h": "#A783FA", "acc_bg": "#10203F",
        "acc_line": "#21407F", "acc2_bg": "#1A1438",
        "ok": "#2FE5A7", "ok_bg": "#0A2620", "ok_line": "#165440", "ok_hover": "#0F3329",
        "warn": "#FFB443", "warn_bg": "#291E0B", "warn_line": "#5A4113",
        "bad": "#FF5A73", "bad_h": "#FF7C90", "bad_bg": "#2B101A", "bad_line": "#5B2033",
        "logbg": "#04070E", "pink": "#D17BF5", "cyan": "#36C8F5", "knob": "#C3CAD6", "shade": "#010309",
    },
    "light": {
        "bg": "#EDF1F8", "side": "#F6F8FC", "surf": "#FDFDFF", "surf2": "#F3F6FB", "hover": "#E8EDF6",
        "line": "#DDE4EF", "line2": "#CBD4E3", "line3": "#B0BCD0",
        "text": "#0D1424", "sub": "#4D5970", "mute": "#8892A7",
        "acc": "#2563EB", "acc_h": "#1D4FD0", "acc2": "#7C3AED", "acc2_h": "#6928D9", "acc_bg": "#E4ECFE",
        "acc_line": "#B5C9FB", "acc2_bg": "#EFE7FE",
        "ok": "#0B9F6E", "ok_bg": "#E0F5EC", "ok_line": "#A3DEC6", "ok_hover": "#CDEEDF",
        "warn": "#B86E00", "warn_bg": "#FFF2DB", "warn_line": "#EFCD92",
        "bad": "#DC2F4A", "bad_h": "#E84A62", "bad_bg": "#FCE6EA", "bad_line": "#F2B3BE",
        "logbg": "#F4F6FA", "pink": "#A94BD6", "cyan": "#0A8FBF", "knob": "#FCFCFE", "shade": "#22314F",
    },
}
T = dict(THEMES["dark"])  # поточна палітра; змінюється на місці (set_theme), тож `from ui_kit import T` бачить нову
THEME = {"name": "dark"}
MOTION = {"on": True}  # плавні анімації (у налаштуваннях можна вимкнути — для слабких ПК і тих, кого вони втомлюють)


def dur(ms: int) -> int:
    """Тривалість анімації з урахуванням налаштування «Плавні анімації»."""
    return ms if MOTION["on"] else 0


def is_dark() -> bool:
    return THEME["name"] == "dark"


def qc(key: str, alpha: int = 255) -> QColor:
    """Колір палітри з прозорістю: qc("acc", 60)."""
    c = QColor(T[key])
    c.setAlpha(alpha)
    return c


IMPACT_COLOR = {"habits": "bad", "medium": "warn", "safe": "acc"}

QSS = """
QWidget { color: @text; }
QWidget#root, QWidget#page, QDialog { background: @bg; }
QFrame#side { background: @side; border-right: 1px solid @line; }
QWidget#sideNav { background: transparent; }
QLabel { background: transparent; }
QLabel#display { font-size: 28px; font-weight: 700; }
QLabel#hero { font-size: 46px; font-weight: 700; }
QLabel#h1 { font-size: 26px; font-weight: 700; }
QLabel#h2 { font-size: 16px; font-weight: 600; }
QLabel#h3 { font-size: 14px; font-weight: 600; }
QLabel#brand { font-size: 16px; font-weight: 700; }
QLabel#sub { color: @sub; font-size: 13px; }
QLabel#desc { color: @sub; font-size: 12px; }
QLabel#muted { color: @mute; font-size: 12px; }
QLabel#micro { color: @mute; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLabel#navcap { color: @mute; font-size: 11px; padding: 8px 14px 3px 14px; }
QLabel#rowTitle { font-size: 14px; }
QLabel#value { font-size: 15px; font-weight: 600; }
QLabel#big { font-size: 26px; font-weight: 700; }
QLabel#mono { font-family: 'Cascadia Mono', Consolas, monospace; color: @sub; font-size: 11px;
              background: @logbg; border: 1px solid @line; border-radius: 8px; padding: 8px 10px; }
QLabel#note { background: @surf; border: 1px solid @line; border-radius: 10px; padding: 10px 14px;
              color: @sub; font-size: 12px; }
QLabel#warnNote { color: @warn; font-size: 12px; padding: 8px 14px 4px 14px; }
QLabel#stepNum { background: @surf2; border: 1px solid @line2; border-radius: 12px; color: @sub;
                 font-size: 12px; font-weight: 600; }

QFrame#card { background: @surf; border: 1px solid @line; border-radius: 16px; }
QFrame#card:hover { border-color: @line2; }
QFrame#cardAccent { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 @acc_bg, stop:0.55 @surf, stop:1 @acc2_bg);
                    border: 1px solid @acc_line; border-radius: 18px; }
QFrame#glass { background: @surf; border: 1px solid @line2; border-radius: 20px; }
QFrame#row { background: transparent; border-radius: 10px; }
QFrame#row:hover { background: @surf2; }
QFrame#bar { background: @side; border-top: 1px solid @line; }
QFrame#banner { background: @bad_bg; border: 1px solid @bad_line; border-radius: 14px; }
QFrame#bannerWarn { background: @warn_bg; border: 1px solid @warn_line; border-radius: 14px; }
QFrame#bannerInfo { background: @acc_bg; border: 1px solid @acc_line; border-radius: 14px; }
QFrame#toast { background: @surf2; border: 1px solid @line3; border-radius: 14px; }
QFrame#segbar { background: @surf; border: 1px solid @line; border-radius: 12px; }

QPushButton { background: @surf2; border: 1px solid @line2; border-radius: 10px; padding: 8px 16px; color: @text; }
QPushButton:hover { background: @hover; border-color: @line3; }
QPushButton:pressed { background: @surf; }
QPushButton:disabled { color: @mute; background: @surf; border-color: @line; }
QPushButton:focus { border-color: @acc; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @acc, stop:1 @acc2); border: none;
                      color: #FFFFFF; font-weight: 600; padding: 10px 22px; border-radius: 12px; }
QPushButton#primary:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @acc_h, stop:1 @acc2_h); }
QPushButton#primary:pressed { background: @acc; }
QPushButton#primary:disabled { background: @surf2; color: @mute; }
QPushButton#danger { background: @bad; border: 1px solid @bad; color: #FFFFFF; font-weight: 600; padding: 10px 22px;
                     border-radius: 12px; }
QPushButton#danger:hover { background: @bad_h; border-color: @bad_h; }
QPushButton#good { background: @ok_bg; border: 1px solid @ok_line; color: @ok; padding: 10px 20px; border-radius: 12px; }
QPushButton#good:hover { background: @ok_hover; border-color: @ok; }
QPushButton#good:disabled { color: @mute; background: @surf; border-color: @line; }
QPushButton#ghost { background: transparent; border: none; color: @acc; padding: 4px 8px; }
QPushButton#ghost:hover { color: @acc_h; }
QPushButton#ghost:disabled { color: @mute; }
QPushButton#sideUpd { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @acc, stop:1 @acc2); border: none;
                      color: #FFFFFF; font-weight: 600; padding: 8px 12px; border-radius: 10px; text-align: left; }
QPushButton#sideUpd:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @acc_h, stop:1 @acc2_h); }
QPushButton#nav { text-align: left; background: transparent; border: none; border-radius: 10px;
                  padding: 7px 14px; color: @sub; font-size: 14px; }
QPushButton#nav:hover { background: @surf; color: @text; }
QPushButton#nav:checked { background: @acc_bg; color: @text; font-weight: 600; }
QPushButton#seg { background: transparent; border: none; border-radius: 9px; padding: 7px 18px; color: @sub;
                  font-weight: 600; }
QPushButton#seg:hover { color: @text; }
QPushButton#seg:checked { background: @acc; color: #FFFFFF; }
QPushButton#chip { background: transparent; border: 1px solid @line2; border-radius: 15px; padding: 5px 13px;
                   color: @sub; font-size: 12px; }
QPushButton#chip:hover { color: @text; border-color: @line3; }
QPushButton#chip:checked { background: @acc_bg; border-color: @acc; color: @text; }

QLineEdit, QSpinBox, QComboBox { background: @surf; border: 1px solid @line2; border-radius: 10px; padding: 7px 10px;
                                 selection-background-color: @acc; selection-color: #FFFFFF; }
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: @acc; }
QComboBox QAbstractItemView { background: @surf2; border: 1px solid @line2; selection-background-color: @acc_bg; }

QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @line2; border-radius: 3px; min-height: 36px; margin: 0 2px; }
QScrollBar::handle:vertical:hover { background: @line3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @line2; border-radius: 3px; min-width: 36px; margin: 2px 0; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QPlainTextEdit#log { background: @logbg; border: 1px solid @line; border-radius: 14px; padding: 8px 10px;
                     color: @sub; selection-background-color: @acc_bg; }
QProgressBar { background: @surf2; border: none; border-radius: 4px; }
QProgressBar#sizebar { background: @surf2; border-radius: 3px; }
QProgressBar#sizebar::chunk { background: @acc; border-radius: 3px; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 @acc, stop:1 @acc2); border-radius: 4px; }
QSlider::groove:horizontal { height: 4px; background: @line2; border-radius: 2px; }
QSlider::handle:horizontal { background: @text; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QToolTip { background: @surf2; color: @text; border: 1px solid @line2; padding: 6px 8px; }
QMenu { background: @surf2; border: 1px solid @line2; padding: 6px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; }
QMenu::item:selected { background: @acc_bg; }
QMenu::separator { height: 1px; background: @line2; margin: 4px 8px; }
"""


def build_qss() -> str:
    s = QSS
    for k in sorted(T, key=len, reverse=True):  # довші ключі першими: @acc_h раніше за @acc
        s = s.replace("@" + k, T[k])
    return s


def app_palette() -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: T["bg"], QPalette.ColorRole.WindowText: T["text"],
        QPalette.ColorRole.Base: T["surf"], QPalette.ColorRole.AlternateBase: T["surf2"],
        QPalette.ColorRole.Text: T["text"], QPalette.ColorRole.Button: T["surf2"],
        QPalette.ColorRole.ButtonText: T["text"], QPalette.ColorRole.Highlight: T["acc"],
        QPalette.ColorRole.HighlightedText: "#FFFFFF", QPalette.ColorRole.ToolTipBase: T["surf2"],
        QPalette.ColorRole.ToolTipText: T["text"], QPalette.ColorRole.PlaceholderText: T["mute"],
        QPalette.ColorRole.Link: T["acc"],
    }
    for role, col in roles.items():
        pal.setColor(role, QColor(col))
    return pal


def system_theme() -> str:
    """Тема Windows для програм («Персоналізація → Кольори»): dark | light."""
    try:
        from PyQt6.QtGui import QGuiApplication
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Light:
            return "light"
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
    except Exception:
        pass
    if E.IS_WIN:
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return "light" if winreg.QueryValueEx(k, "AppsUseLightTheme")[0] else "dark"
        except OSError:
            pass
    return "dark"


def resolve_theme(pref) -> str:
    """Налаштування теми (system | dark | light) -> палітра."""
    return pref if pref in THEMES else system_theme()


class ThemeBus(QObject):
    """Сповіщає віджети, які малюють щось заздалегідь (іконки, кеші), що палітра змінилася."""
    changed = pyqtSignal(str)


THEME_BUS = ThemeBus()
_HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")


def remap_hex(text: str, remap: dict) -> str:
    return _HEX.sub(lambda m: remap.get(m.group(0).upper(), m.group(0)), text)


def _remap_value(v, remap: dict):
    if isinstance(v, QColor):
        n = remap.get(v.name().upper())
        if n:
            c = QColor(n)
            c.setAlpha(v.alpha())
            return c
        return v
    if isinstance(v, str) and len(v) == 7 and v.startswith("#"):
        return remap.get(v.upper(), v)
    if isinstance(v, list) and v and all(isinstance(x, tuple) for x in v):  # ряди графіків [(значення, колір)]
        return [tuple(_remap_value(y, remap) for y in x) for x in v]
    return v


def remap_widget(w: QWidget, remap: dict) -> None:
    """Перефарбувати один віджет: рядок стилю з уже підставленими кольорами і збережені кольори (Ring.c тощо)."""
    try:
        ss = w.styleSheet()
        if ss and "#" in ss:
            new = remap_hex(ss, remap)
            if new != ss:
                w.setStyleSheet(new)
        for k, v in list(vars(w).items()):
            nv = _remap_value(v, remap)
            if nv is not v:
                setattr(w, k, nv)
        if hasattr(w, "retheme"):
            w.retheme()
    except RuntimeError:  # віджет уже знищено на боці C++
        pass


_APP = {"qss": None}  # тема, з якою стоїть стиль усієї програми (app.setStyleSheet)


def apply_app_theme(app) -> None:
    """Стиль усієї програми. Повна перебудова стилю займає понад секунду на кількох тисячах віджетів, тож під час
    роботи її робимо лише тоді, коли вікно сховане (flush_app_theme)."""
    app.setPalette(app_palette())
    app.setStyleSheet(build_qss())
    _APP["qss"] = THEME["name"]


def style_window(w: QWidget) -> None:
    """Вікно, відкрите після перемикання теми наживо, отримує стиль нової теми на рівні вікна (у 4–5 разів швидше,
    ніж перебудова стилю всієї програми). Вікна з власним стилем не чіпаємо."""
    if w.styleSheet() and not getattr(w, "_ox_qss", False):
        return
    want = "" if THEME["name"] == _APP["qss"] else build_qss()
    if w.styleSheet() != want:
        w._ox_qss = bool(want)
        w.setStyleSheet(want)


def flush_app_theme(app=None) -> None:
    """Коли вікно сховане (у треї): привести стиль усієї програми до поточної теми й прибрати стилі рівня вікон."""
    if app is None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
    if app is None or _APP["qss"] == THEME["name"]:
        return
    apply_app_theme(app)
    for w in app.topLevelWidgets():
        if getattr(w, "_ox_qss", False):
            w._ox_qss = False
            w.setStyleSheet("")


def set_theme(name: str, app=None) -> bool:
    """Перемкнути палітру наживо. -> чи щось змінилося."""
    if name not in THEMES or THEMES[name] == T:
        THEME["name"] = name if name in THEMES else THEME["name"]
        return False
    old = dict(T)
    new = THEMES[name]
    remap = {old[k].upper(): new[k] for k in new if k in old}
    T.clear()
    T.update(new)
    THEME["name"] = name
    if app is None:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
    if app is not None:
        if _APP["qss"] is None or not app.topLevelWidgets():
            apply_app_theme(app)  # ще до створення вікон — дешево
        else:
            app.setPalette(app_palette())
            for w in app.topLevelWidgets():
                if w.isWindow() and (w.isVisible() or getattr(w, "_ox_qss", False)):
                    style_window(w)
        for w in app.allWidgets():
            remap_widget(w, remap)
        for w in app.topLevelWidgets():
            if w.isWindow() and w.isVisible():
                dark_titlebar(w)
        for w in app.allWidgets():
            w.update()
    THEME_BUS.changed.emit(name)
    return True


def make_font(px: int, weight=QFont.Weight.Normal, mono=False) -> QFont:
    f = QFont()
    f.setFamilies(["Cascadia Mono", "Consolas", "DejaVu Sans Mono", "monospace"] if mono else
                  ["Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans"])
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def mix(a: QColor, b: QColor, k: float) -> QColor:
    return QColor(int(a.red() + (b.red() - a.red()) * k), int(a.green() + (b.green() - a.green()) * k),
                  int(a.blue() + (b.blue() - a.blue()) * k))


def dark_titlebar(w: QWidget) -> None:
    """Заголовок вікна Windows у тон теми: темний або світлий, колір — як у бічної панелі. Вікна, що відкриваються
    після перемикання теми наживо, тут же отримують її стиль (style_window)."""
    if w.isWindow() and _APP["qss"] is not None and _APP["qss"] != THEME["name"]:
        style_window(w)
    if not E.IS_WIN:
        return
    try:
        hwnd, on = ctypes.c_void_p(int(w.winId())), ctypes.c_int(1 if is_dark() else 0)
        dwm = ctypes.windll.dwmapi
        if dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), 4) != 0:
            dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(on), 4)
        c = QColor(T["side"])
        ref = ctypes.c_int(c.red() | (c.green() << 8) | (c.blue() << 16))
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(ref), 4)
    except Exception:
        pass


# ───────────────────────── іконки ─────────────────────────
def _canvas(size: int):
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(2)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pm, p


def icon_pixmap(name: str, color: str, size: int = 20) -> QPixmap:
    pm, p = _canvas(size)
    p.scale(size / 24, size / 24)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    if name == "pulse":
        path.moveTo(3, 12); path.lineTo(7, 12); path.lineTo(9.5, 6); path.lineTo(13.5, 18); path.lineTo(16, 12)
        path.lineTo(21, 12)
    elif name == "wand":
        path.moveTo(4, 20); path.lineTo(14.5, 9.5)
        path.moveTo(16, 3); path.lineTo(16, 7); path.moveTo(14, 5); path.lineTo(18, 5)
        path.moveTo(20, 9); path.lineTo(20, 12); path.moveTo(18.5, 10.5); path.lineTo(21.5, 10.5)
        path.moveTo(9, 3.5); path.lineTo(9, 6); path.moveTo(7.75, 4.75); path.lineTo(10.25, 4.75)
    elif name == "gamepad":
        path.addRoundedRect(QRectF(2.5, 7, 19, 11), 5.5, 5.5)
        path.moveTo(7.5, 10.5); path.lineTo(7.5, 14.5); path.moveTo(5.5, 12.5); path.lineTo(9.5, 12.5)
        p.drawPath(path)
        path = QPainterPath()
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(15.5, 11.2), 0.9, 0.9)
        p.drawEllipse(QPointF(17.6, 13.6), 0.9, 0.9)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "chip":
        path.addRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
        path.addRect(QRectF(9.5, 9.5, 5, 5))
        for v in (9.5, 14.5):
            path.moveTo(v, 3); path.lineTo(v, 6); path.moveTo(v, 18); path.lineTo(v, 21)
            path.moveTo(3, v); path.lineTo(6, v); path.moveTo(18, v); path.lineTo(21, v)
    elif name == "hwc":  # Hardware Center: плата з «пульсом» перевірки
        path.addRoundedRect(QRectF(3.5, 4.5, 17, 15), 2.5, 2.5)
        path.moveTo(6, 12.5); path.lineTo(9, 12.5); path.lineTo(10.5, 9); path.lineTo(13, 16); path.lineTo(14.5, 12.5)
        path.lineTo(18, 12.5)
    elif name == "laptop":
        path.addRoundedRect(QRectF(5, 5, 14, 10), 1.5, 1.5)
        path.moveTo(2.5, 18.5); path.lineTo(21.5, 18.5)
    elif name == "broom":
        path.moveTo(19, 3); path.lineTo(12.5, 11.5)
        path.moveTo(9, 10.5); path.lineTo(15, 14.5); path.lineTo(12.5, 20.5); path.lineTo(4, 15.5); path.closeSubpath()
        path.moveTo(8, 17.5); path.lineTo(9.8, 14.2)
    elif name == "rocket":
        path.moveTo(12, 3); path.cubicTo(16, 6, 16.5, 11, 15, 15); path.lineTo(9, 15)
        path.cubicTo(7.5, 11, 8, 6, 12, 3)
        path.addEllipse(QPointF(12, 9), 1.6, 1.6)
        path.moveTo(9, 13); path.lineTo(6.5, 16.5); path.lineTo(9.5, 16)
        path.moveTo(15, 13); path.lineTo(17.5, 16.5); path.lineTo(14.5, 16)
        path.moveTo(11, 18); path.lineTo(11, 20.5); path.moveTo(13, 18); path.lineTo(13, 20.5)
    elif name == "palette":
        path.moveTo(12, 3.5)
        path.cubicTo(6.5, 3.5, 3.5, 7.5, 3.5, 12); path.cubicTo(3.5, 17, 7.5, 20.5, 11.5, 20.5)
        path.cubicTo(13.5, 20.5, 13.5, 18.5, 12.8, 17.5); path.cubicTo(12, 16, 13, 14.5, 14.7, 14.5)
        path.lineTo(16.5, 14.5); path.cubicTo(19, 14.5, 20.5, 12.8, 20.5, 10.8); path.cubicTo(20.5, 6.5, 16.5, 3.5, 12, 3.5)
        p.drawPath(path)
        path = QPainterPath()
        p.setBrush(QColor(color))
        for x, y in ((8, 10), (11, 7), (15.5, 8)):
            p.drawEllipse(QPointF(x, y), 1.1, 1.1)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "shield":
        path.moveTo(12, 3); path.lineTo(19.5, 6); path.lineTo(19.5, 11.5)
        path.cubicTo(19.5, 16, 16.5, 19.3, 12, 21); path.cubicTo(7.5, 19.3, 4.5, 16, 4.5, 11.5)
        path.lineTo(4.5, 6); path.closeSubpath()
        path.moveTo(8.8, 12); path.lineTo(11.2, 14.4); path.lineTo(15.4, 9.8)
    elif name == "gear":
        path.addEllipse(QPointF(12, 12), 3, 3)
        import math
        for i in range(8):
            a = i * math.pi / 4
            path.moveTo(12 + 6.2 * math.cos(a), 12 + 6.2 * math.sin(a))
            path.lineTo(12 + 8.6 * math.cos(a), 12 + 8.6 * math.sin(a))
        path.addEllipse(QPointF(12, 12), 6.2, 6.2)
    elif name == "sliders":
        knobs = ((6, 15), (12, 8), (18, 13))
        for y, _ in knobs:
            path.moveTo(4, y); path.lineTo(20, y)
        p.drawPath(path)
        path = QPainterPath()
        p.setBrush(QColor(T["surf"]))
        for y, x in knobs:
            p.drawEllipse(QPointF(x, y), 2.4, 2.4)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "chevron":
        path.moveTo(9, 6); path.lineTo(15, 12); path.lineTo(9, 18)
    elif name == "gauge":
        path.moveTo(4.2, 17.5); path.cubicTo(2.2, 12.5, 5.5, 5.5, 12, 5.5); path.cubicTo(18.5, 5.5, 21.8, 12.5, 19.8, 17.5)
        path.moveTo(12, 15); path.lineTo(16, 9.5)
        p.drawPath(path)
        path = QPainterPath()
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(12, 15), 1.7, 1.7)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "globe":
        path.addEllipse(QPointF(12, 12), 8.5, 8.5)
        path.moveTo(3.5, 12); path.lineTo(20.5, 12)
        path.moveTo(12, 3.5); path.cubicTo(7.8, 7.5, 7.8, 16.5, 12, 20.5)
        path.moveTo(12, 3.5); path.cubicTo(16.2, 7.5, 16.2, 16.5, 12, 20.5)
    elif name == "box":
        for x, y in ((4, 4), (13, 4), (4, 13), (13, 13)):
            path.addRoundedRect(QRectF(x, y, 7, 7), 2, 2)
    elif name == "bolt":
        path.moveTo(13.5, 2.8); path.lineTo(5.5, 13.2); path.lineTo(11.4, 13.2); path.lineTo(10.4, 21.2)
        path.lineTo(18.5, 10.6); path.lineTo(12.6, 10.6); path.closeSubpath()
    elif name == "library":  # три обкладинки ігор на полиці
        path.addRoundedRect(QRectF(3.5, 5, 5, 14), 1.4, 1.4)
        path.addRoundedRect(QRectF(9.5, 5, 5, 14), 1.4, 1.4)
        path.moveTo(16.2, 6.2); path.lineTo(20.6, 5.2); path.lineTo(21.6, 18.4); path.lineTo(17.2, 19.4)
        path.closeSubpath()
        path.moveTo(2.5, 21); path.lineTo(21.5, 21)
    elif name == "block":
        path.addEllipse(QPointF(12, 12), 8.6, 8.6)
        path.moveTo(5.9, 5.9); path.lineTo(18.1, 18.1)
    elif name == "ram":  # планка пам'яті
        path.addRoundedRect(QRectF(2.5, 7, 19, 9), 1.6, 1.6)
        for x in (6.5, 10.5, 14.5):
            path.addRect(QRectF(x, 9.5, 2.6, 4))
        for x in (5, 8, 11, 14, 17, 20):
            path.moveTo(x - 0.5, 16); path.lineTo(x - 0.5, 18.5)
    elif name == "disk":
        path.addRoundedRect(QRectF(3, 6, 18, 12), 2.5, 2.5)
        path.moveTo(3, 13.5); path.lineTo(21, 13.5)
        p.drawPath(path)
        path = QPainterPath()
        p.setBrush(QColor(color))
        p.drawEllipse(QPointF(17.3, 15.8), 0.9, 0.9)
        p.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "thermo":
        path.moveTo(10, 14.2); path.lineTo(10, 5.5)
        path.cubicTo(10, 3.2, 14, 3.2, 14, 5.5); path.lineTo(14, 14.2)
        path.cubicTo(16.6, 15.6, 16, 20.5, 12, 20.5); path.cubicTo(8, 20.5, 7.4, 15.6, 10, 14.2)
        path.moveTo(12, 9); path.lineTo(12, 16.5)
    elif name == "panel":  # бічна панель (закріпити меню)
        path.addRoundedRect(QRectF(3.5, 4.5, 17, 15), 2.5, 2.5)
        path.moveTo(9.5, 4.5); path.lineTo(9.5, 19.5)
        path.moveTo(13, 9.5); path.lineTo(15.5, 12); path.lineTo(13, 14.5)
    elif name == "download":
        path.moveTo(12, 4); path.lineTo(12, 15)
        path.moveTo(7.5, 10.5); path.lineTo(12, 15); path.lineTo(16.5, 10.5)
        path.moveTo(5, 19.5); path.lineTo(19, 19.5)
    elif name == "sun":
        path.addEllipse(QPointF(12, 12), 4, 4)
        import math
        for i in range(8):
            a = i * math.pi / 4
            path.moveTo(12 + 6.6 * math.cos(a), 12 + 6.6 * math.sin(a))
            path.lineTo(12 + 8.8 * math.cos(a), 12 + 8.8 * math.sin(a))
    elif name == "moon":
        path.moveTo(19.5, 14.5)
        path.cubicTo(17.5, 19.5, 10.5, 21, 6.8, 17.2); path.cubicTo(3, 13.4, 4.4, 6.4, 9.5, 4.5)
        path.cubicTo(8, 9, 10.5, 13.8, 15, 15); path.cubicTo(16.5, 15.4, 18.2, 15.2, 19.5, 14.5)
    elif name == "monitor":
        path.addRoundedRect(QRectF(3, 4.5, 18, 12), 2, 2)
        path.moveTo(9, 20); path.lineTo(15, 20); path.moveTo(12, 16.5); path.lineTo(12, 20)
    elif name == "sparkle":
        path.moveTo(12, 3); path.cubicTo(12.8, 8.5, 15.5, 11.2, 21, 12)
        path.cubicTo(15.5, 12.8, 12.8, 15.5, 12, 21); path.cubicTo(11.2, 15.5, 8.5, 12.8, 3, 12)
        path.cubicTo(8.5, 11.2, 11.2, 8.5, 12, 3)
    p.drawPath(path)
    p.end()
    return pm


def nav_icon(name: str) -> QIcon:
    ic = QIcon()
    ic.addPixmap(icon_pixmap(name, T["sub"]), QIcon.Mode.Normal, QIcon.State.Off)
    ic.addPixmap(icon_pixmap(name, T["acc_h"]), QIcon.Mode.Normal, QIcon.State.On)
    return ic


def logo_pixmap(size: int = 40) -> QPixmap:
    path = asset("icon.png")
    if path:
        pm = QPixmap(path)
        if not pm.isNull():
            pm = pm.scaled(size * 2, size * 2, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            pm.setDevicePixelRatio(2)
            return pm
    pm, p = _canvas(size)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, QColor(T["acc"]))
    g.setColorAt(1, QColor(T["acc2"]))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.26, size * 0.26)
    pen = QPen(QColor(255, 255, 255, 150), size * 0.13)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    a, b = size * 0.31, size * 0.69
    p.drawLine(QPointF(b, a), QPointF(a, b))
    pen.setColor(QColor("#FFFFFF"))
    p.setPen(pen)
    p.drawLine(QPointF(a, a), QPointF(b, b))
    p.end()
    return pm


def png_icon(name: str):
    path = asset(name)
    if not path:
        return None
    pm = QPixmap(path)
    return None if pm.isNull() else QIcon(pm)


# ───────────────────────── дрібні помічники ─────────────────────────
def label(text: str = "", obj: str = None, wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    return lb


def button(text: str, obj: str = None, cb=None) -> QPushButton:
    b = QPushButton(text)
    if obj:
        b.setObjectName(obj)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    if cb:
        b.clicked.connect(lambda _=False: cb())
    return b


def card(obj: str = "card") -> QFrame:
    f = QFrame()
    f.setObjectName(obj)
    return f


def vbox(w: QWidget = None, margins=(0, 0, 0, 0), spacing: int = 0) -> QVBoxLayout:
    v = QVBoxLayout(w) if w is not None else QVBoxLayout()
    v.setContentsMargins(*margins)
    v.setSpacing(spacing)
    return v


def hbox(w: QWidget = None, margins=(0, 0, 0, 0), spacing: int = 0) -> QHBoxLayout:
    h = QHBoxLayout(w) if w is not None else QHBoxLayout()
    h.setContentsMargins(*margins)
    h.setSpacing(spacing)
    return h


BADGE = {
    "muted": ("sub", "surf2", "line2"), "acc": ("acc_h", "acc_bg", "acc_line"), "ok": ("ok", "ok_bg", "ok_line"),
    "warn": ("warn", "warn_bg", "warn_line"), "bad": ("bad", "bad_bg", "bad_line"),
}


def style_badge(lb: QLabel, text: str, kind: str) -> QLabel:
    fg, bg, bd = (T[k] for k in BADGE.get(kind, BADGE["muted"]))
    lb.setText(text)
    lb.setStyleSheet(f"color:{fg};background:{bg};border:1px solid {bd};border-radius:9px;"
                     f"padding:1px 8px;font-size:11px;")
    return lb


def badge(text: str, kind: str = "muted") -> QLabel:
    lb = style_badge(QLabel(), text, kind)
    lb.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return lb


def dot(color: str, size: int = 8) -> QLabel:
    d = QLabel()
    d.setFixedSize(size, size)
    d.setStyleSheet(f"background:{color};border-radius:{size // 2}px;")
    return d


def styled(w: QWidget, obj: str) -> QWidget:
    w.setObjectName(obj)
    w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return w


def scroller(inner: QWidget) -> QScrollArea:
    styled(inner, "page")
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    sa.setWidget(inner)
    return sa


def page_header(title: str, sub: str, right: QWidget = None) -> QWidget:
    w = QWidget()
    h = hbox(w, (32, 24, 32, 14))
    v = vbox(spacing=3)
    v.addWidget(label(title, "h1"))
    v.addWidget(label(sub, "sub", wrap=True))
    h.addLayout(v, 1)
    if right is not None:
        h.addWidget(right, 0, Qt.AlignmentFlag.AlignBottom)
    return w


def bottom_bar() -> tuple:
    bar = QFrame()
    bar.setObjectName("bar")
    h = hbox(bar, (32, 14, 32, 14), 12)
    return bar, h


def clear_layout(lay) -> None:
    while lay.count():
        it = lay.takeAt(0)
        if it.widget():
            it.widget().deleteLater()
        elif it.layout():
            clear_layout(it.layout())


def section_card(title: str, sub: str = None) -> tuple:
    c = card()
    v = vbox(c, (8, 14, 8, 8), 2)
    head = vbox(margins=(14, 0, 14, 6), spacing=2)
    head.addWidget(label(title, "h2"))
    if sub:
        head.addWidget(label(sub, "desc", wrap=True))
    v.addLayout(head)
    return c, v


def log_html(line: str) -> str:
    st = line.strip()
    col, weight = T["sub"], 400
    if "✓" in st:
        col = T["ok"]
    elif "⚠" in st:
        col = T["warn"]
    elif "✗" in st:
        col = T["bad"]
    elif st.startswith(("[►]", "[↩]", "[⚡]")):
        col, weight = T["text"], 600
    elif st.startswith(("═", "─")):
        col = T["line3"]
    elif "█" in st or "░" in st:
        col = T["acc"]
    elif "[dry-run]" in st:
        col = T["mute"]
    text = html.escape(line).replace(" ", "&nbsp;") or "&nbsp;"
    return f'<span style="color:{col};font-weight:{weight}">{text}</span>'


def append_log(widget: QPlainTextEdit, text: str) -> None:
    for part in str(text).split("\n"):
        widget.appendHtml(log_html(part))
    sb = widget.verticalScrollBar()
    sb.setValue(sb.maximum())


class LogBus(QObject):
    """Спільний журнал швидких дій: його показують кілька сторінок."""
    line = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.history = []

    def write(self, text: str) -> None:
        self.history.append(text)
        del self.history[:-600]
        self.line.emit(text)


LOG = LogBus()


class LogView(QPlainTextEdit):
    def __init__(self, height: int = 120):
        super().__init__()
        self.setObjectName("log")
        self.setReadOnly(True)
        self.setFont(make_font(12, mono=True))
        self.setMaximumBlockCount(2000)
        self.setFixedHeight(height)
        for h in LOG.history[-200:]:
            append_log(self, h)
        LOG.line.connect(lambda s: append_log(self, s))

    def retheme(self):
        """Кольори рядків журналу вшиті в HTML — після зміни теми перемальовуємо історію."""
        self.clear()
        for h in LOG.history[-200:]:
            append_log(self, h)


# ───────────────────────── віджети ─────────────────────────
class Switch(QAbstractButton):
    """Перемикач у стилі Windows 11 з плавною анімацією."""

    def __init__(self, color: str = None, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(42, 24)
        self._k = 0.0
        self._c = QColor(color or T["acc"])
        self._a = QPropertyAnimation(self, b"knob", self)
        self._a.setDuration(150)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._animate)

    def _get(self):
        return self._k

    def _set(self, v):
        self._k = float(v)
        self.update()

    knob = pyqtProperty(float, _get, _set)

    def _animate(self, on):
        self._a.stop()
        self._a.setDuration(dur(170))
        self._a.setStartValue(self._k)
        self._a.setEndValue(1.0 if on else 0.0)
        self._a.start()

    def set_quiet(self, on: bool) -> None:
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        self._a.stop()
        self._k = 1.0 if on else 0.0
        self.update()

    def sizeHint(self):
        return QSize(42, 24)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(mix(QColor(T["line2"]), self._c, self._k))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - 6 - d) * self._k
        if not is_dark():  # на світлому тлі біла кулька без тіні губиться
            p.setBrush(QColor(0, 0, 0, 28))
            p.drawEllipse(QRectF(x, r.top() + 3.8, d, d))
        p.setBrush(mix(QColor(T["knob"]), QColor("#FFFFFF"), self._k))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        if self.hasFocus():
            p.setPen(QPen(QColor(T["acc_h"]), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), r.height() / 2, r.height() / 2)


class Check(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedSize(20, 20)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, 18, 18)
        if self.isChecked():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T["acc"]))
            p.drawRoundedRect(r, 5, 5)
            pen = QPen(QColor("#FFFFFF"), 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            path = QPainterPath()
            path.moveTo(5.5, 10.2); path.lineTo(8.6, 13.3); path.lineTo(14.5, 6.8)
            p.drawPath(path)
        else:
            p.setPen(QPen(QColor(T["acc"] if self.hasFocus() else T["line3"]), 1.4))
            p.setBrush(QColor(T["surf"]))
            p.drawRoundedRect(r, 5, 5)


class Ring(QWidget):
    """Кільцевий індикатор (відсотки)."""

    def __init__(self, color: str, size: int = 96, width: int = 8, font_px: int = 20):
        super().__init__()
        self.setFixedSize(size, size)
        self._v = 0.0
        self.c = QColor(color)
        self.w = width
        self.font_px = font_px
        self.text = None
        self._a = QPropertyAnimation(self, b"val", self)
        self._a.setDuration(700)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get(self):
        return self._v

    def _set(self, v):
        self._v = float(v)
        self.update()

    val = pyqtProperty(float, _get, _set)

    def set_value(self, v: float, color: str = None) -> None:
        if color:
            self.c = QColor(color)
        self._a.stop()
        self._a.setDuration(dur(900))
        self._a.setStartValue(self._v)
        self._a.setEndValue(max(0.0, min(1.0, v)))
        self._a.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.w
        r = QRectF(w / 2 + 1, w / 2 + 1, self.width() - w - 2, self.height() - w - 2)
        pen = QPen(QColor(T["line"]), w)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, 0, 360 * 16)
        if self._v > 0.004:
            glow = QColor(self.c)
            glow.setAlpha(46)
            gp = QPen(glow, w + 5)
            gp.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(gp)
            p.drawArc(r, 90 * 16, -int(self._v * 360 * 16))
            pen.setColor(self.c)
            p.setPen(pen)
            p.drawArc(r, 90 * 16, -int(self._v * 360 * 16))
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(self.font_px, QFont.Weight.DemiBold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text or f"{round(self._v * 100)}%")


class Spark(QWidget):
    """Графік часу кадрів (або будь-якого ряду): лінія, сітка й підписи мінімуму та максимуму."""

    def __init__(self, height: int = 120, unit: str = "ms"):
        super().__init__()
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.series = []  # [(значення, колір)]
        self.unit = unit

    def set_series(self, series) -> None:
        self.series = [(list(v), c) for v, c in series if v]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(T["line"]), 1))
        p.setBrush(QColor(T["logbg"]))
        p.drawRoundedRect(r, 10, 10)
        vals = [v for s, _ in self.series for v in s]
        if not vals:
            p.setPen(QColor(T["mute"]))
            p.setFont(make_font(12))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "—")
            return
        lo, hi = min(vals) * 0.85, max(vals) * 1.08 or 1.0
        if hi - lo < 1:
            lo, hi = max(0.0, lo - 1), hi + 1
        pad_l, pad_r, pad_t, pad_b = 44, 12, 10, 14
        w, h = r.width() - pad_l - pad_r, r.height() - pad_t - pad_b
        p.setFont(make_font(10))
        for k in range(4):
            y = pad_t + h * k / 3
            p.setPen(QPen(QColor(T["line"]), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(pad_l, y), QPointF(pad_l + w, y))
            p.setPen(QColor(T["mute"]))
            p.drawText(QRectF(4, y - 8, pad_l - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{hi - (hi - lo) * k / 3:.0f}")
        for s, col in self.series:
            path = QPainterPath()
            n = max(1, len(s) - 1)
            for i, v in enumerate(s):
                pt = QPointF(pad_l + w * i / n, pad_t + h * (1 - (v - lo) / (hi - lo)))
                path.moveTo(pt) if i == 0 else path.lineTo(pt)
            pen = QPen(QColor(col), 1.6)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)


class Bars(QWidget):
    """Стовпчики за добу (як у Pi-hole): усі запити й заблоковані поверх них."""

    def __init__(self, height: int = 150):
        super().__init__()
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.data = []  # [(слот, усього, заблоковано)]
        self.slot = 600

    def set_data(self, data, slot: int = 600) -> None:
        self.data = [tuple(x) for x in data or []]
        self.slot = slot
        self.update()

    def paintEvent(self, _):
        import time as _time
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(T["line"]), 1))
        p.setBrush(QColor(T["logbg"]))
        p.drawRoundedRect(r, 10, 10)
        top = max([t for _, t, _ in self.data] or [0])
        if not top:
            p.setPen(QColor(T["mute"]))
            p.setFont(make_font(12))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "—")
            return
        hi = top * 1.1
        pad_l, pad_r, pad_t, pad_b = 44, 12, 10, 24
        w, h = r.width() - pad_l - pad_r, r.height() - pad_t - pad_b
        p.setFont(make_font(10))
        for k in range(4):
            y = pad_t + h * k / 3
            p.setPen(QPen(QColor(T["line"]), 1, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(pad_l, y), QPointF(pad_l + w, y))
            p.setPen(QColor(T["mute"]))
            p.drawText(QRectF(4, y - 8, pad_l - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{max(0.0, hi - hi * k / 3):.0f}")
        n = len(self.data)
        bw = w / n
        allowed = QColor(T["acc"])
        allowed.setAlpha(95)
        blocked = QColor(T["acc2"])
        for i, (slot, total, blk) in enumerate(self.data):
            x = pad_l + i * bw
            p.setPen(Qt.PenStyle.NoPen)
            if total:
                th = h * total / hi
                p.setBrush(allowed)
                p.drawRoundedRect(QRectF(x + 0.5, pad_t + h - th, max(1.0, bw - 1.0), th), 1, 1)
            if blk:
                bh = h * blk / hi
                p.setBrush(blocked)
                p.drawRoundedRect(QRectF(x + 0.5, pad_t + h - bh, max(1.0, bw - 1.0), bh), 1, 1)
            lt = _time.localtime(slot * self.slot)
            if lt.tm_min * 60 < self.slot and lt.tm_hour % 3 == 0 and 2 < i < n - 2:
                p.setPen(QColor(T["mute"]))
                p.drawText(QRectF(x - 24, pad_t + h + 5, 48, 14), Qt.AlignmentFlag.AlignCenter, f"{lt.tm_hour:02d}:00")


class ProfileCard(QAbstractButton):
    def __init__(self, pd: dict):
        super().__init__()
        self.pd = pd
        self.c = QColor(pd["color"])
        self.active = False
        self.recommended = False
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(76)
        self.setMinimumWidth(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(tr(f"prof.{pd['key']}.desc"))

    def set_active(self, on: bool) -> None:
        self.active = on
        self.update()

    def set_recommended(self, on: bool) -> None:
        self.recommended = on
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        bg = QColor(T["surf2"] if self._hover else T["surf"])
        if self.active:
            bg = mix(bg, self.c, 0.13)
            p.setPen(QPen(self.c, 1.5))
        else:
            p.setPen(QPen(QColor(T["line2"] if self._hover or self.hasFocus() else T["line"]), 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, 12, 12)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.c)
        p.drawRoundedRect(QRectF(14, 16, 4, r.height() - 32), 2, 2)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(14, QFont.Weight.DemiBold))
        p.drawText(QRectF(28, 13, r.width() - 34, 22), Qt.AlignmentFlag.AlignVCenter,
                   tr(f"prof.{self.pd['key']}.name"))
        p.setPen(self.c if self.active else QColor(T["sub"]))
        p.setFont(make_font(12))
        p.drawText(QRectF(28, 35, r.width() - 34, 18), Qt.AlignmentFlag.AlignVCenter,
                   tr(f"prof.{self.pd['key']}.sub"))
        if self.recommended:
            p.setPen(QColor(T["ok"]))
            p.setFont(make_font(11, QFont.Weight.DemiBold))
            p.drawText(QRectF(28, 53, r.width() - 34, 16), Qt.AlignmentFlag.AlignVCenter, tr("opt.recommended"))


class OptionCard(QAbstractButton):
    """Варіант відповіді в майстрі: назва, пояснення, індикатор вибору."""

    def __init__(self, title: str, desc: str, multi: bool = False):
        super().__init__()
        self.title, self.desc, self.multi = title, desc, multi
        self._hover = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setMinimumHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        on = self.isChecked()
        acc = QColor(T["acc"])
        p.setPen(QPen(acc if on else QColor(T["line2"] if self._hover or self.hasFocus() else T["line"]),
                      1.5 if on else 1))
        p.setBrush(mix(QColor(T["surf2"] if self._hover else T["surf"]), acc, 0.10 if on else 0))
        p.drawRoundedRect(r, 12, 12)
        cx, cy = 26, r.center().y()
        if self.multi:
            box = QRectF(cx - 9, cy - 9, 18, 18)
            p.setPen(QPen(acc if on else QColor(T["line3"]), 1.5))
            p.setBrush(acc if on else Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(box, 5, 5)
            if on:
                pen = QPen(QColor("#FFFFFF"), 2)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                path = QPainterPath()
                path.moveTo(cx - 4.5, cy); path.lineTo(cx - 1.4, cy + 3.1); path.lineTo(cx + 4.5, cy - 3.4)
                p.drawPath(path)
        else:
            p.setPen(QPen(acc if on else QColor(T["line3"]), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            if on:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(acc)
                p.drawEllipse(QPointF(cx, cy), 5, 5)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(14, QFont.Weight.DemiBold))
        p.drawText(QRectF(50, 12, r.width() - 64, 22), Qt.AlignmentFlag.AlignVCenter, self.title)
        p.setPen(QColor(T["sub"]))
        p.setFont(make_font(12))
        flags = (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop).value | Qt.TextFlag.TextWordWrap.value
        p.drawText(QRectF(50, 36, r.width() - 64, r.height() - 42), flags, self.desc)


class Segmented(QFrame):
    changed = pyqtSignal(int)

    def __init__(self, items):
        super().__init__()
        self.setObjectName("segbar")
        h = hbox(self, (3, 3, 3, 3), 2)
        self.btns = []
        for i, text in enumerate(items):
            b = QPushButton(text)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            b.clicked.connect(lambda _=False, i=i: self.select(i, True))
            h.addWidget(b)
            self.btns.append(b)
        self.select(0)

    def select(self, i: int, emit: bool = False) -> None:
        for j, b in enumerate(self.btns):
            b.setChecked(j == i)
        if emit:
            self.changed.emit(i)


class FlowLayout(QLayout):
    """Елементи в рядок із перенесенням, кожен — своєї ширини (чипи розділів): у сітці з рівними колонками довгі
    назви обрізались («агностика Windo»)."""

    def __init__(self, parent=None, hspacing: int = 6, vspacing: int = 6):
        super().__init__(parent)
        self._items = []
        self._h, self._v = hspacing, vspacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._place(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._place(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _place(self, rect, test: bool) -> int:
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line = r.x(), r.y(), 0
        for it in self._items:
            w = it.sizeHint()
            if x + w.width() > r.right() + 1 and line:
                x, y, line = r.x(), y + line + self._v, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), w))
            x += w.width() + self._h
            line = max(line, w.height())
        return y + line - rect.y() + m.bottom()


def chip(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setObjectName("chip")
    b.setCheckable(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    return b


class Toast(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        h = hbox(self, (16, 11, 18, 11), 10)
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.text = QLabel()
        self.text.setStyleSheet("font-size:13px;")
        h.addWidget(self.dot)
        h.addWidget(self.text)
        self.eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.eff)
        self.anim = QPropertyAnimation(self.eff, b"opacity", self)
        self.anim.finished.connect(self._after)
        self.slide = QPropertyAnimation(self, b"pos", self)
        self.slide.setEasingCurve(QEasingCurve.Type.OutBack)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)
        self.hide()

    def show_msg(self, text: str, kind: str = "ok", area: QRectF = None) -> None:
        self.dot.setStyleSheet(f"background:{T.get(kind, T['ok'])};border-radius:4px;")
        self.text.setText(text)
        self.adjustSize()
        a = area or QRectF(self.parent().rect())
        end = QPoint(int(a.left() + (a.width() - self.width()) / 2), int(a.bottom() - self.height() - 92))
        start = self.eff.opacity() if self.isVisible() else 0.0
        self.anim.stop()
        self.eff.setOpacity(start)
        self.raise_()
        self.show()
        self.slide.stop()
        self.slide.setDuration(dur(320))
        self.slide.setStartValue(end + QPoint(0, 0 if start > 0.5 else 18))
        self.slide.setEndValue(end)
        self.move(self.slide.startValue())
        self.slide.start()
        self.anim.setDuration(dur(220))
        self.anim.setStartValue(start)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self.timer.start(3400)

    def _fade_out(self):
        self.anim.stop()
        self.anim.setDuration(dur(350))
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()

    def _after(self):
        if self.eff.opacity() < 0.05:
            self.hide()


# ───────────────────────── фонові задачі й діалоги ─────────────────────────
class Worker(QThread):
    """Виконує job(log, progress) у фоні. У кожної дії свій токен скасування (self.cancel): усередині job
    E.CANCEL — саме він, тож «Зупинити» однієї дії не чіпає інших, а нова дія не скидає чужу зупинку."""
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)
    result = pyqtSignal(object)

    def __init__(self, job):
        super().__init__()
        self.job = job
        self.cancel = E.CancelToken()

    def stop(self) -> None:
        self.cancel.set()

    @property
    def cancelled(self) -> bool:
        return self.cancel.is_set()

    def run(self):
        E.bind_cancel(self.cancel)
        try:
            res = self.job(self.log.emit, self.progress.emit)
        except Exception as e:  # помилка не повинна валити інтерфейс
            self.log.emit(tr("e.err", err=f"{type(e).__name__}: {e}"))
            res = {"error": str(e)}
        finally:
            E.bind_cancel(None)
        self.result.emit(res)


def outcome(res, cancelled: bool = False):
    """Підсумок фонової дії -> (стан, кількість невдач). Стан: "error" — дія перервана помилкою, "stopped" —
    зупинив користувач, "partial" — завершено, але частина операцій не вдалася, "ok" — усе вдалося.
    Розуміє результати apply_tweaks / undo_ids (fail, partial), WinGet (fail) та {"ok": False}."""
    r = res if isinstance(res, dict) else {}
    if r.get("error"):
        return "error", 0
    if cancelled or r.get("cancelled"):
        return "stopped", 0
    bad = 0
    for k in ("fail", "partial"):
        try:
            bad += int(r.get(k) or 0)
        except (TypeError, ValueError):
            bad += 1
    if not bad and r.get("ok") is False:
        bad = 1
    return ("partial", bad) if bad else ("ok", 0)


def fade_in_window(w: QWidget, ms: int = 200) -> None:
    """Плавна поява окремого вікна (діалогу). На платформах без прозорості вікон нічого не робить."""
    if not MOTION["on"] or getattr(w, "_faded", False):
        return
    w._faded = True
    try:
        w.setWindowOpacity(0.0)
        a = QPropertyAnimation(w, b"windowOpacity", w)
        a.setDuration(ms)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    except Exception:
        w.setWindowOpacity(1.0)


class Ask(QDialog):
    def __init__(self, parent, title: str, text: str, ok: str = None, cancel: str = None, kind: str = "primary"):
        super().__init__(parent)
        self.setWindowTitle(E.APP_TITLE)
        self.setModal(True)
        self.setMinimumWidth(500)
        v = vbox(self, (26, 24, 26, 20), 10)
        v.addWidget(label(title, "h2", wrap=True))
        body = label(text, "sub", wrap=True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        v.addWidget(body)
        v.addSpacing(10)
        h = hbox(spacing=8)
        h.addStretch()
        if cancel is not False:
            h.addWidget(button(cancel or tr("btn.cancel"), None, self.reject))
        ok_btn = button(ok or tr("btn.continue"), kind, self.accept)
        ok_btn.setDefault(True)
        h.addWidget(ok_btn)
        v.addLayout(h)

    def showEvent(self, e):
        dark_titlebar(self)
        fade_in_window(self)
        super().showEvent(e)

    @staticmethod
    def ask(parent, title, text, ok=None, kind="primary") -> bool:
        return Ask(parent, title, text, ok, None, kind).exec() == QDialog.DialogCode.Accepted

    @staticmethod
    def info(parent, title, text) -> None:
        Ask(parent, title, text, tr("btn.ok"), False).exec()


class RunDialog(QDialog):
    """Консоль виконання: прогрес, кольоровий журнал, зупинка та перезавантаження."""

    def __init__(self, parent, title: str, job):
        super().__init__(parent)
        self.setWindowTitle(f"{E.APP_TITLE} — {title}")
        self.setModal(True)
        self.resize(900, 620)
        self.finished_ok = False
        self.res = {}
        v = vbox(self, (24, 22, 24, 20), 12)
        top = hbox()
        top.addWidget(label(title, "h2"))
        top.addStretch()
        self.state = badge(tr("run.running"), "acc")
        top.addWidget(self.state)
        v.addLayout(top)
        self.step = label(tr("run.prepare"), "desc")
        v.addWidget(self.step)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setRange(0, 0)
        v.addWidget(self.bar)
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setFont(make_font(12, mono=True))
        self.log.setMaximumBlockCount(8000)
        v.addWidget(self.log, 1)
        h = hbox(spacing=8)
        self.btn_reboot = button(tr("run.reboot"), "good", self._reboot)
        self.btn_reboot.hide()
        h.addWidget(self.btn_reboot)
        self.btn_failed = button(tr("run.show_failed"), None, self._show_failed)
        self.btn_failed.hide()
        h.addWidget(self.btn_failed)
        h.addStretch()
        self.btn_main = button(tr("run.stop"), None, self._main_clicked)
        h.addWidget(self.btn_main)
        v.addLayout(h)
        self.worker = Worker(job)
        self.worker.log.connect(self._log)
        self.worker.progress.connect(self._progress)
        self.worker.result.connect(self._done)
        self.worker.start()

    def _log(self, s: str):
        append_log(self.log, s)
        LOG.write(s)

    def showEvent(self, e):
        dark_titlebar(self)
        fade_in_window(self)
        super().showEvent(e)

    def _progress(self, i: int, total: int, text: str):
        self.bar.setRange(0, max(total, 1))
        self.bar.setValue(min(i, total))
        if total > 10000:  # завантаження: i й total — байти, а не кроки («Крок 1048577 з 48200000»)
            self.step.setText(text)
            return
        self.step.setText(tr("run.step", i=i + 1, n=total, what=text) if i < total else tr("run.finishing"))

    def _done(self, res):
        self.worker.wait()
        self.finished_ok = True
        self.res = res if isinstance(res, dict) else {}
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        stopped = self.worker.cancelled
        self.outcome, bad = outcome(self.res, stopped)
        reboot = " " + tr("run.need_reboot") if self.res.get("reboot") else ""
        if self.outcome == "error":
            style_badge(self.state, tr("run.error"), "bad")
            self.step.setText(tr("run.error_text"))
        elif self.outcome == "stopped":
            style_badge(self.state, tr("run.stopped"), "warn")
            self.step.setText(tr("run.stopped_text"))
        elif self.outcome == "partial":  # 6.15: не зелене «Готово», коли частина операцій не вдалася
            style_badge(self.state, tr("run.partial", n=bad), "warn")
            self.step.setText(tr("run.partial_text") + reboot)
        else:
            style_badge(self.state, tr("run.done"), "ok")
            self.step.setText(tr("run.done_text") + reboot)
        self.btn_failed.setVisible(self.outcome == "partial" and bool(self.res.get("failed_items")))
        self.btn_main.setText(tr("btn.close"))
        self.btn_main.setEnabled(True)
        self.btn_main.setObjectName("primary")
        self.btn_main.style().unpolish(self.btn_main)
        self.btn_main.style().polish(self.btn_main)
        self.btn_reboot.setVisible(bool(self.res.get("reboot")) and not stopped)
        self.btn_main.setFocus()

    def _show_failed(self):
        items = self.res.get("failed_items") or []
        Ask.info(self, tr("run.failed_t"), "\n".join(f"• {x}" for x in items))

    def _main_clicked(self):
        if self.finished_ok:
            self.accept()
            return
        self.worker.stop()
        self.btn_main.setEnabled(False)
        self.btn_main.setText(tr("run.stopping"))
        self.step.setText(tr("run.stopping_text"))

    def _reboot(self):
        if Ask.ask(self, tr("run.reboot_q"), tr("run.reboot_text"), tr("run.reboot_btn")):
            E.run(f'shutdown /r /t 10 /c "{E.APP_NAME}"', 10)
            self.accept()

    def reject(self):
        if self.finished_ok:
            super().reject()
        else:
            self.step.setText(tr("run.wait"))

    def closeEvent(self, e):
        if self.finished_ok:
            e.accept()
        else:
            e.ignore()
            self.reject()
