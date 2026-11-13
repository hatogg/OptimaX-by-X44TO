"""
OptimaX — рух і нові елементи інтерфейсу (6.13): плавні переходи між сторінками, бічне меню, що розгортається при
наведенні, скляні вікна дій поверх програми, заставка, кругове перемикання теми, живі графіки, радар оцінки,
кільце-шкала, анімована галочка й лічильники, що «набігають».

Усе малюється QPainter-ом і бере кольори з ui_kit.T під час малювання — тож і світла, і темна теми працюють без
перебудови віджетів. Тривалість кожної анімації — через ui_kit.dur(): з вимкненими «Плавними анімаціями» все
відбувається одразу.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import (Qt, QTimer, QVariantAnimation, QEasingCurve, QRectF, QPointF, QPoint, QRect, QSize,
                          pyqtSignal, QEventLoop)
from PyQt6.QtGui import (QColor, QPainter, QPen, QPainterPath, QFont, QLinearGradient, QRadialGradient, QPixmap,
                         QConicalGradient)
from PyQt6.QtWidgets import (QWidget, QFrame, QStackedWidget, QAbstractButton, QGraphicsOpacityEffect, QLabel,
                             QSizePolicy, QApplication)

import ui_kit as UK
from ui_kit import T, qc, make_font, mix, icon_pixmap, logo_pixmap, vbox, hbox, dur

OUT = QEasingCurve.Type.OutCubic
INOUT = QEasingCurve.Type.InOutCubic


# ───────────────────────── анімація значення ─────────────────────────
class Anim:
    """Одна анімація числа на віджет: to(1.0) — плавно, з поточного значення. setter(v) кличеться на кожен кадр."""

    def __init__(self, owner, setter, ms: int = 300, curve=OUT, value: float = 0.0):
        self.value = float(value)
        self.ms = ms
        self._setter = setter
        self._done = None
        self.a = QVariantAnimation(owner)
        self.a.setEasingCurve(curve)
        self.a.valueChanged.connect(self._on)
        self.a.finished.connect(self._fin)

    def _on(self, v):
        self.value = float(v)
        self._setter(self.value)

    def _fin(self):
        cb, self._done = self._done, None
        if cb:
            cb()

    def to(self, end: float, start: float = None, ms: int = None, done=None, curve=None) -> None:
        self.a.stop()
        self._done = done
        s = self.value if start is None else float(start)
        d = dur(self.ms if ms is None else ms)
        if d <= 0 or abs(s - end) < 1e-9:
            self._on(end)
            self._fin()
            return
        if curve is not None:
            self.a.setEasingCurve(curve)
        self.a.setStartValue(s)
        self.a.setEndValue(float(end))
        self.a.setDuration(d)
        self.a.start()

    def set(self, v: float) -> None:
        self.a.stop()
        self._on(v)

    @property
    def running(self) -> bool:
        return self.a.state() == QVariantAnimation.State.Running


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def level_color(frac: float) -> QColor:
    """Колір навантаження: спокійно — акцент/м'ятний, багато — жовтий, критично — червоний."""
    return QColor(T["bad"] if frac >= 0.9 else T["warn"] if frac >= 0.8 else T["ok"])


# ───────────────────────── переходи між сторінками ─────────────────────────
class _Transition(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # 6.14: перехід зафарбовує все сам — Qt не перемальовує на кожному кадрі сторінку під ним (з живими графіками)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.old = self.new = None
        self.t = 1.0
        self.anim = Anim(self, self._step, 300, OUT)
        self.hide()

    def start(self, old: QPixmap, new: QPixmap) -> None:
        self.old, self.new = old, new
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self.anim.to(1.0, 0.0, done=self._end)

    def _step(self, t):
        self.t = t
        self.update()

    def _end(self):
        self.hide()
        self.old = self.new = None

    def paintEvent(self, _):
        if self.old is None:
            return
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(T["bg"]))
        t = self.t
        p.setOpacity(max(0.0, 1.0 - t * 1.6))
        p.drawPixmap(QPointF(0, -10 * t), self.old)
        p.setOpacity(min(1.0, t * 1.25))
        p.drawPixmap(QPointF(0, 18 * (1 - t)), self.new)


class FadeStack(QStackedWidget):
    """QStackedWidget з переходом: стара сторінка тане й зсувається вгору, нова підіймається знизу."""

    def __init__(self):
        super().__init__()
        self._tr = _Transition(self)

    def setCurrentWidget(self, w):
        old = self.currentWidget()
        animate = (old is not None and old is not w and self.isVisible() and UK.MOTION["on"]
                   and self.width() > 50 and self.indexOf(w) >= 0)
        if not animate:
            return super().setCurrentWidget(w)
        pm_old = old.grab()
        super().setCurrentWidget(w)
        self._tr.start(pm_old, w.grab())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._tr.setGeometry(self.rect())

    @property
    def animating(self) -> bool:
        """Іде перехід між сторінками — важку роботу в потоці інтерфейсу краще відкласти (Main._build_pages)."""
        return self._tr.anim.running


# ───────────────────────── бічне меню ─────────────────────────
RAIL_MIN, RAIL_MAX = 76, 252


class _RailPart(QWidget):
    """Частина меню, що знає, наскільки меню розгорнуте (rail.k від 0 до 1)."""

    def __init__(self, rail):
        super().__init__()
        self.rail = rail

    @property
    def k(self) -> float:
        return self.rail.k


class Brand(_RailPart):
    def __init__(self, rail, name: str, by: str, tag: str = ""):
        super().__init__(rail)
        self.name, self.by, self.tag = name, by, tag
        self.logo = logo_pixmap(36)
        self.setFixedHeight(48)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        cy = self.height() / 2
        # світіння за логотипом
        g = QRadialGradient(QPointF(26, cy), 30)
        g.setColorAt(0, qc("acc", 70 if UK.is_dark() else 40))
        g.setColorAt(1, qc("acc", 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(26, cy), 30, 30)
        p.drawPixmap(QPointF(8, cy - 18), self.logo)
        if self.k <= 0.02:
            return
        p.setOpacity(self.k)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(17, QFont.Weight.Bold))
        p.drawText(QRectF(56, cy - 20, 200, 22), Qt.AlignmentFlag.AlignVCenter, self.name)
        p.setPen(QColor(T["mute"]))
        f = make_font(10, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(f)
        p.drawText(QRectF(57, cy + 2, 200, 16), Qt.AlignmentFlag.AlignVCenter, self.tag or self.by)


class NavCap(_RailPart):
    """Заголовок групи меню: розгорнуте — підпис, згорнуте — коротка риска."""

    def __init__(self, rail, text: str):
        super().__init__(rail)
        self._text = text
        self.setFixedHeight(24)

    def text(self) -> str:
        return self._text

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        k = self.k
        if k < 0.98:
            p.setOpacity(1 - k)
            p.setPen(QPen(QColor(T["line2"]), 1.4))
            y = self.height() / 2 + 2
            p.drawLine(QPointF(18, y), QPointF(34, y))
        if k > 0.02:
            p.setOpacity(k)
            p.setPen(QColor(T["mute"]))
            f = make_font(10, QFont.Weight.Bold)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
            p.setFont(f)
            p.drawText(QRectF(14, 6, self.width() - 20, self.height() - 6), Qt.AlignmentFlag.AlignVCenter,
                       self._text.upper())


class NavItem(QAbstractButton):
    """Пункт меню: іконка завжди на місці, підпис з'являється, коли меню розгортається."""

    def __init__(self, rail, text: str, icon: str):
        super().__init__()
        self.rail = rail
        self.icon_name = icon
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.hov = 0.0
        self._ha = Anim(self, self._set_hov, 160)
        self._cache = {}

    def _set_hov(self, v):
        self.hov = v
        self.update()

    def enterEvent(self, e):
        self._ha.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._ha.to(0.0)
        super().leaveEvent(e)

    def _icon(self, color: QColor) -> QPixmap:
        key = color.name()
        pm = self._cache.get(key)
        if pm is None:
            if len(self._cache) > 24:
                self._cache.clear()
            pm = self._cache[key] = icon_pixmap(self.icon_name, key, 20)
        return pm

    def moveEvent(self, e):
        super().moveEvent(e)
        if self.isChecked():
            self.rail.snap_indicator()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.isChecked():
            self.rail.snap_indicator()

    def sizeHint(self):
        return QSize(RAIL_MAX - 24, 36)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0, 1, 0, -1)
        on = self.isChecked()
        if self.hov > 0.01 and not on:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc("hover", int(255 * self.hov)))
            p.drawRoundedRect(r, 10, 10)
        if on:
            col = QColor(T["acc_h"] if UK.is_dark() else T["acc"])
        else:
            col = mix(QColor(T["sub"]), QColor(T["text"]), self.hov)
        p.drawPixmap(QPointF(16, r.center().y() - 10), self._icon(col))
        k = self.rail.k
        if k > 0.02:
            p.setOpacity(k)
            p.setPen(QColor(T["text"]) if on else col)
            p.setFont(make_font(14, QFont.Weight.DemiBold if on else QFont.Weight.Normal))
            p.drawText(QRectF(50 - 8 * (1 - k), r.top(), r.width() - 56, r.height()), Qt.AlignmentFlag.AlignVCenter,
                       self.text())
            p.setOpacity(1.0)
        if self.hasFocus():
            p.setPen(QPen(QColor(T["acc_h"]), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), 10, 10)


class NavIndicator(QWidget):
    """Підсвітка вибраного пункту: переїжджає між пунктами, а не перестрибує."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._from = self._to = QRectF()
        self.anim = Anim(self, self._step, 320, OUT)

    def move_to(self, rect: QRect, animate: bool = True) -> None:
        target = QRectF(rect).adjusted(0, 1, 0, -1)
        cur = QRectF(self.geometry())
        if not animate or not self.isVisible() or cur.isEmpty():
            self.anim.set(1.0)
            self._from = self._to = target
            self.setGeometry(target.toRect())
            self.show()
            self.lower()
            return
        self._from, self._to = cur, target
        self.anim.to(1.0, 0.0)

    def _step(self, t):
        a, b = self._from, self._to
        r = QRectF(lerp(a.x(), b.x(), t), lerp(a.y(), b.y(), t), lerp(a.width(), b.width(), t),
                   lerp(a.height(), b.height(), t))
        self.setGeometry(r.toRect())
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, qc("acc", 64 if UK.is_dark() else 40))
        g.setColorAt(1, qc("acc", 18 if UK.is_dark() else 14))
        p.setPen(QPen(qc("acc", 70 if UK.is_dark() else 60), 1))
        p.setBrush(g)
        p.drawRoundedRect(r, 10, 10)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T["acc"]))
        p.drawRoundedRect(QRectF(0, r.center().y() - 8, 3, 16), 1.5, 1.5)


class StatusLine(_RailPart):
    """Крапка стану й підпис (режим перегляду, права адміністратора, режим гри, версія)."""

    def __init__(self, rail, color_key: str = None, text: str = ""):
        super().__init__(rail)
        self.color_key = color_key
        self._text = text
        self.setFixedHeight(22)

    def setText(self, text: str) -> None:
        self._text = text
        self.update()

    def text(self) -> str:
        return self._text

    def set_color(self, key: str) -> None:
        self.color_key = key
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cy = self.height() / 2
        if self.color_key:
            c = QColor(T[self.color_key])
            g = QRadialGradient(QPointF(26, cy), 9)
            g.setColorAt(0, qc(self.color_key, 90))
            g.setColorAt(1, qc(self.color_key, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(26, cy), 9, 9)
            p.setBrush(c)
            p.drawEllipse(QPointF(26, cy), 3.6, 3.6)
        if self.rail.k > 0.02:
            p.setOpacity(self.rail.k)
            p.setPen(QColor(T["mute"]))
            p.setFont(make_font(12))
            x = 42 if self.color_key else 16
            p.drawText(QRectF(x, 0, self.width() - x - 4, self.height()), Qt.AlignmentFlag.AlignVCenter,
                       self._text)


class RailButton(QAbstractButton):
    """Кнопка внизу меню (закріпити меню, оновлення): у згорнутому меню — лише іконка."""

    def __init__(self, rail, icon: str, text: str = "", accent: bool = False):
        super().__init__()
        self.rail = rail
        self.icon_name = icon
        self.accent = accent
        self.flip = False
        self.setText(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(36 if accent else 32)
        self.hov = 0.0
        self._ha = Anim(self, self._set_hov, 150)

    def _set_hov(self, v):
        self.hov = v
        self.update()

    def enterEvent(self, e):
        self._ha.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._ha.to(0.0)
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.accent:
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, mix(QColor(T["acc"]), QColor(T["acc_h"]), self.hov))
            g.setColorAt(1, mix(QColor(T["acc2"]), QColor(T["acc2_h"]), self.hov))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(r, 11, 11)
            col = QColor("#FFFFFF")
        else:
            if self.hov > 0.01:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(qc("hover", int(255 * self.hov)))
                p.drawRoundedRect(r, 10, 10)
            col = mix(QColor(T["mute"]), QColor(T["text"]), self.hov)
        pm = icon_pixmap(self.icon_name, col.name(), 18)
        cy = r.center().y()
        p.save()
        p.translate(26, cy)
        if self.flip:
            p.rotate(180)
        p.drawPixmap(QPointF(-9, -9), pm)
        p.restore()
        if self.rail.k > 0.02 and self.text():
            p.setOpacity(self.rail.k)
            p.setPen(col)
            p.setFont(make_font(13, QFont.Weight.DemiBold if self.accent else QFont.Weight.Normal))
            p.drawText(QRectF(48, 0, r.width() - 52, r.height()), Qt.AlignmentFlag.AlignVCenter, self.text())


class ScrollFade(QWidget):
    """Згасання біля краю прокручуваного меню: видно, що нижче (чи вище) є ще пункти."""

    def __init__(self, area, bottom: bool = True):
        super().__init__(area)
        self.area = area
        self.bottom = bottom
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sb = area.verticalScrollBar()
        sb.valueChanged.connect(self.sync)
        sb.rangeChanged.connect(lambda *_: self.sync())
        self.sync()

    def sync(self, *_):
        sb = self.area.verticalScrollBar()
        more = sb.value() < sb.maximum() if self.bottom else sb.value() > sb.minimum()
        h = 28
        self.setGeometry(0, self.area.height() - h if self.bottom else 0, self.area.width(), h)
        self.setVisible(more)
        self.raise_()

    def paintEvent(self, _):
        p = QPainter(self)
        g = QLinearGradient(0, 0, 0, self.height())
        a, b = (qc("side", 0), qc("side", 255)) if self.bottom else (qc("side", 255), qc("side", 0))
        g.setColorAt(0, a)
        g.setColorAt(1, b)
        p.fillRect(self.rect(), g)


class RailShadow(QWidget):
    """Тінь праворуч від розгорнутого меню, що лежить поверх сторінки."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.k = 0.0

    def paintEvent(self, _):
        if self.k <= 0.01:
            return
        p = QPainter(self)
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0, qc("shade", int((150 if UK.is_dark() else 80) * self.k)))
        g.setColorAt(1, qc("shade", 0))
        p.fillRect(self.rect(), g)


# ───────────────────────── скляне вікно поверх програми ─────────────────────────
def blurred(pm: QPixmap, factor: int = 10) -> QPixmap:
    """Швидке розмиття: зменшити й збільшити назад зі згладжуванням (двічі — м'якше)."""
    if pm.isNull():
        return pm
    w, h = pm.width(), pm.height()
    small = pm.scaled(max(1, w // factor), max(1, h // factor), Qt.AspectRatioMode.IgnoreAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)
    mid = small.scaled(max(1, w // 3), max(1, h // 3), Qt.AspectRatioMode.IgnoreAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    out = mid.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    out.setDevicePixelRatio(pm.devicePixelRatio())
    return out


class GlassSheet(QWidget):
    """Модальне «скляне» вікно всередині головного: розмитий і притемнений фон, картка виїжджає й проявляється.
    Наповнення — у self.body (QVBoxLayout). close_sheet() ховає з анімацією."""
    closed = pyqtSignal()

    def __init__(self, host: QWidget, width: int = 460, closable: bool = True):
        super().__init__(host)
        self.host = host
        self.closable = closable
        self.t = 0.0
        self.bg = None
        self.card = QFrame(self)
        self.card.setObjectName("glass")
        self.card.setFixedWidth(width)
        self.body = vbox(self.card, (26, 24, 26, 22), 12)
        self.eff = QGraphicsOpacityEffect(self.card)
        self.eff.setOpacity(0.0)
        self.card.setGraphicsEffect(self.eff)
        self.anim = Anim(self, self._step, 340, OUT)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide()

    def open(self) -> None:
        self.bg = blurred(self.host.grab())
        self.setGeometry(self.host.rect())
        self.raise_()
        self.show()
        self.setFocus()
        self._place()
        self.anim.to(1.0, 0.0)

    def close_sheet(self) -> None:
        self.anim.to(0.0, ms=240, done=self._gone, curve=QEasingCurve.Type.InCubic)

    def _gone(self):
        self.hide()
        self.closed.emit()
        self.deleteLater()

    def _step(self, t):
        self.t = t
        self.eff.setOpacity(t)
        self.raise_()
        self._place()
        self.update()

    def _place(self):
        self.card.adjustSize()
        cw, ch = self.card.width(), self.card.sizeHint().height()
        self.card.resize(cw, ch)
        x = (self.width() - cw) // 2
        y = (self.height() - ch) // 2 + int(22 * (1 - self.t))
        self.card.move(x, y)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape and self.closable:
            self.close_sheet()
            return
        super().keyPressEvent(e)

    def mousePressEvent(self, e):
        e.accept()  # під склом нічого не натискається

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.bg is not None:
            p.setOpacity(self.t)
            p.drawPixmap(self.rect(), self.bg)
            p.setOpacity(1.0)
        p.fillRect(self.rect(), qc("shade", int((150 if UK.is_dark() else 70) * self.t)))
        # м'яка тінь і світіння під карткою
        cr = QRectF(self.card.geometry())
        p.setPen(Qt.PenStyle.NoPen)
        base = 16 if UK.is_dark() else 5
        for i in range(8):
            p.setBrush(qc("shade", int(base * self.t * (1 - i / 8))))
            d = 2 + i * 4
            p.drawRoundedRect(cr.adjusted(-d, -d + 12, d, d + 16), 20 + d, 20 + d)
        gc = QPointF(cr.center().x(), cr.top())
        rad = cr.width() * 0.75
        g = QRadialGradient(gc, rad)
        g.setColorAt(0, qc("acc", int(38 * self.t)))
        g.setColorAt(0.6, qc("acc", int(10 * self.t)))
        g.setColorAt(1, qc("acc", 0))
        p.setBrush(g)
        p.drawEllipse(gc, rad, rad)


# ───────────────────────── кругове перемикання теми ─────────────────────────
class ThemeReveal(QWidget):
    """Знімок вікна в старій темі, у якому розростається коло з новою темою."""

    def __init__(self, host: QWidget, old: QPixmap, origin: QPoint):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.old = old
        self.origin = QPointF(origin)
        self.r = 0.0
        self.setGeometry(host.rect())
        corners = [QPointF(0, 0), QPointF(self.width(), 0), QPointF(0, self.height()),
                   QPointF(self.width(), self.height())]
        self.r_max = max(math.hypot(c.x() - self.origin.x(), c.y() - self.origin.y()) for c in corners) + 4
        self.anim = Anim(self, self._step, 620, INOUT)
        self.raise_()
        self.show()

    def start(self) -> None:
        self.raise_()
        self.anim.to(1.0, 0.0, done=self.deleteLater)

    def _step(self, t):
        self.r = self.r_max * t
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        path.addRect(QRectF(self.rect()))
        path.addEllipse(self.origin, self.r, self.r)
        p.setClipPath(path)
        p.drawPixmap(0, 0, self.old)
        p.setClipping(False)
        if 0 < self.r < self.r_max:
            p.setPen(QPen(qc("acc", 110), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(self.origin, self.r, self.r)


def reveal_theme(window: QWidget, name: str, origin: QPoint = None) -> None:
    """Перемкнути тему з круговою анімацією від точки origin (координати вікна)."""
    if not UK.MOTION["on"] or not window.isVisible():
        UK.set_theme(name)
        return
    old = window.grab()
    ov = ThemeReveal(window, old, origin or QPoint(window.width() // 2, window.height() // 2))
    QApplication.processEvents()
    UK.set_theme(name)
    ov.start()


# ───────────────────────── заставка ─────────────────────────
class Splash(QWidget):
    """Заставка під час запуску: логотип зі світінням, назва, бігуча смужка. finish(window) — плавно передає
    місце головному вікну."""

    def __init__(self, title: str, sub: str):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(440, 300)
        self.title, self.sub = title, sub
        self.logo = logo_pixmap(84)
        self.t = 0.0      # поява
        self.spin = 0.0   # бігуча смужка
        # 6.14: 350 мс замість 700 — головне вікно почне будуватися лише після вступу, тож довший вступ = довше чекати
        self.anim = Anim(self, self._intro, 350, OUT)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        scr = QApplication.primaryScreen()
        if scr:
            g = scr.availableGeometry()
            self.move(g.center() - QPoint(self.width() // 2, self.height() // 2))

    def _intro(self, t):
        self.t = t
        self.update()

    def _tick(self):
        self.spin = (self.spin + 0.018) % 1.0
        self.update()

    def play(self, then) -> None:
        self.show()
        self.timer.start(16)
        self.anim.to(1.0, 0.0, done=lambda: QTimer.singleShot(60, then))

    def finish(self, window: QWidget) -> None:
        window.setWindowOpacity(0.0)
        window.show()
        # 6.14: перший кадр головного вікна й черга подій після його створення (розкладка, перше малювання, таймери
        # з конструктора) — ≈0,1 с на слабкому ПК. Обробляємо їх, поки вікно ще прозоре, а заставка на місці;
        # інакше вони з'їдали перший кадр передачі, і вона помітно смикалась.
        window.repaint()
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        self.timer.stop()
        self._handed = False

        def step(v):
            if not self._handed:
                self.setWindowOpacity(1 - v)
                window.setWindowOpacity(v)

        def done():
            if self._handed:
                return
            self._handed = True
            self._out.a.stop()  # жодного кроку після передачі: запізнілий крок лишив би вікно напівпрозорим
            window.setWindowOpacity(1.0)
            self.close()
            self.deleteLater()
        # 6.13.1: анімацію тримаємо в self. Як локальну змінну Python знищував її одразу після виходу з finish(),
        # її кроки більше не викликалися — головне вікно лишалося повністю прозорим, а заставка висіла зверху
        # («програма зависла на завантаженні»).
        self._out = Anim(self, step, 420, INOUT)  # м'який початок і кінець — без різкого спалаху вікна
        self._out.to(1.0, 0.0, done=done)
        # запасний шлях: вікно з'явиться, навіть якщо анімація не дійшла до кінця (потік інтерфейсу одразу після
        # появи вікна буває зайнятий кілька секунд — тоді цей таймер спрацьовує раніше за анімацію)
        QTimer.singleShot(1500, done)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        p.setOpacity(min(1.0, self.t * 1.4))
        bg = QLinearGradient(r.topLeft(), r.bottomRight())
        bg.setColorAt(0, QColor(T["surf"]))
        bg.setColorAt(1, QColor(T["bg"]))
        p.setPen(QPen(QColor(T["line2"]), 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, 24, 24)
        c = QPointF(r.center().x(), r.top() + 104)
        glow = QRadialGradient(c, 110)
        glow.setColorAt(0, qc("acc", int(120 * self.t)))
        glow.setColorAt(0.5, qc("acc2", int(36 * self.t)))
        glow.setColorAt(1, qc("acc", 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(c, 150, 110)
        s = 0.7 + 0.3 * self.t
        p.save()
        p.translate(c)
        p.scale(s, s)
        p.drawPixmap(QPointF(-42, -42), self.logo)
        p.restore()
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(26, QFont.Weight.Bold))
        p.drawText(QRectF(r.left(), r.top() + 160 + 10 * (1 - self.t), r.width(), 34), Qt.AlignmentFlag.AlignCenter,
                   self.title)
        p.setPen(QColor(T["mute"]))
        f = make_font(11, QFont.Weight.Bold)
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
        p.setFont(f)
        p.drawText(QRectF(r.left(), r.top() + 196, r.width(), 18), Qt.AlignmentFlag.AlignCenter, self.sub.upper())
        # бігуча смужка
        bar = QRectF(r.center().x() - 70, r.bottom() - 34, 140, 4)
        p.setBrush(QColor(T["line"]))
        p.drawRoundedRect(bar, 2, 2)
        x = bar.left() + (bar.width() + 50) * self.spin - 50
        seg = QRectF(max(bar.left(), x), bar.top(), min(50.0, bar.right() - max(bar.left(), x)), bar.height())
        if seg.width() > 0:
            g = QLinearGradient(seg.topLeft(), seg.topRight())
            g.setColorAt(0, QColor(T["acc"]))
            g.setColorAt(1, QColor(T["acc2"]))
            p.setBrush(g)
            p.drawRoundedRect(seg, 2, 2)


# ───────────────────────── лічильник ─────────────────────────
class CountLabel(QLabel):
    """Число, що «набігає» до нового значення. fmt(v) -> текст."""

    def __init__(self, fmt=lambda v: f"{v:.0f}", obj: str = None, ms: int = 900):
        super().__init__(fmt(0))
        if obj:
            self.setObjectName(obj)
        self.fmt = fmt
        self.target = None
        self.anim = Anim(self, lambda v: self.setText(self.fmt(v)), ms, OUT)

    def set_value(self, v: float, animate: bool = True) -> None:
        self.target = v
        if animate:
            self.anim.to(float(v))
        else:
            self.anim.set(float(v))


# ───────────────────────── шкала-кільце ─────────────────────────
class Gauge(QWidget):
    """Кільце з поділок (як спідометр): світяться поділки до значення, по центру — відсотки й підпис."""

    def __init__(self, size: int = 168, caption: str = "", ticks: int = 54):
        super().__init__()
        self.setFixedSize(size, size)
        self.caption = caption
        self.ticks = ticks
        self.v = 0.0
        self.color_key = None  # None — колір за рівнем
        self.anim = Anim(self, self._set, 900, OUT)

    def _set(self, v):
        self.v = v
        self.update()

    def set_value(self, frac: float, animate: bool = True, ms: int = None) -> None:
        frac = max(0.0, min(1.0, frac))
        if animate:
            self.anim.to(frac, ms=ms)
        else:
            self.anim.set(frac)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        c = QPointF(w / 2, w / 2)
        r_out, r_in = w / 2 - 6, w / 2 - 22
        start, span = 225.0, 270.0  # від лівого низу за годинниковою стрілкою
        lit = self.v * self.ticks
        hi = QColor(T[self.color_key]) if self.color_key else level_color(self.v)
        lo = QColor(T["acc"])
        for i in range(self.ticks):
            a = math.radians(start - span * i / (self.ticks - 1))
            ca, sa = math.cos(a), -math.sin(a)
            p1 = QPointF(c.x() + r_in * ca, c.y() + r_in * sa)
            p2 = QPointF(c.x() + r_out * ca, c.y() + r_out * sa)
            if i < lit:
                col = mix(lo, hi, i / max(1, self.ticks - 1))
                frac_on = min(1.0, lit - i)
                col.setAlpha(int(255 * (0.35 + 0.65 * frac_on)))
                pen = QPen(col, 3.2)
            else:
                pen = QPen(QColor(T["line2"]), 3.2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawLine(p1, p2)
        # кінчик зі світінням
        if self.v > 0.01:
            a = math.radians(start - span * min(1.0, self.v))
            tip = QPointF(c.x() + (r_out + 2) * math.cos(a), c.y() - (r_out + 2) * math.sin(a))
            g = QRadialGradient(tip, 12)
            g.setColorAt(0, QColor(hi.red(), hi.green(), hi.blue(), 200))
            g.setColorAt(1, QColor(hi.red(), hi.green(), hi.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(tip, 12, 12)
        p.setPen(QColor(T["text"]))
        num = f"{round(self.v * 100)}"
        f = make_font(int(w * 0.24), QFont.Weight.Bold)
        p.setFont(f)
        fm = p.fontMetrics()
        nw = fm.horizontalAdvance(num)
        f2 = make_font(int(w * 0.1), QFont.Weight.DemiBold)
        p.setFont(f2)
        pw = p.fontMetrics().horizontalAdvance("%")
        x0 = c.x() - (nw + pw + 2) / 2
        p.setFont(f)
        p.setPen(hi)
        p.drawText(QRectF(x0, c.y() - w * 0.2, nw + 2, w * 0.3), Qt.AlignmentFlag.AlignVCenter, num)
        p.setFont(f2)
        p.drawText(QRectF(x0 + nw + 2, c.y() - w * 0.14, pw + 2, w * 0.3), Qt.AlignmentFlag.AlignVCenter, "%")
        if self.caption:
            p.setPen(QColor(T["mute"]))
            fc = make_font(10, QFont.Weight.Bold)
            fc.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
            p.setFont(fc)
            p.drawText(QRectF(10, c.y() + w * 0.12, w - 20, 18), Qt.AlignmentFlag.AlignCenter, self.caption.upper())


# ───────────────────────── живий графік ─────────────────────────
class LiveGraph(QWidget):
    """Площа під лінією за останні N замірів, з плавним прокручуванням до нового значення.
    values — частки 0…1 (або абсолютні з max_value)."""

    def __init__(self, n: int = 40, height: int = 120, color_key: str = "acc", grid: bool = True,
                 max_value: float = 1.0):
        super().__init__()
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.n = n
        self.vals = []
        self.color_key = color_key
        self.grid = grid
        self.max_value = max_value
        self.shift = 0.0
        self.anim = Anim(self, self._set_shift, 700, QEasingCurve.Type.OutQuad)

    def _set_shift(self, v):
        self.shift = v
        self.update()

    def push(self, v: float) -> None:
        self.vals.append(float(v))
        del self.vals[:-(self.n + 2)]
        self.anim.to(0.0, 1.0)

    def set_values(self, vals) -> None:
        self.vals = [float(v) for v in vals][-(self.n + 2):]
        self.shift = 0.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 4, -1, -1)
        if self.grid:
            p.setPen(QPen(QColor(T["line"]), 1, Qt.PenStyle.DashLine))
            for k in range(1, 4):
                y = r.top() + r.height() * k / 4
                p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
        vals = self.vals[-(self.n + 1):]
        if len(vals) < 2:
            return
        step = r.width() / (self.n - 1)
        off = self.shift * step
        top = self.max_value or 1.0
        pts = []
        for i, v in enumerate(vals):
            x = r.right() - (len(vals) - 1 - i) * step + off
            y = r.bottom() - r.height() * max(0.0, min(1.0, v / top))
            pts.append(QPointF(x, y))
        line = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):  # згладжування: кубічні криві між точками
            mx = (a.x() + b.x()) / 2
            line.cubicTo(QPointF(mx, a.y()), QPointF(mx, b.y()), b)
        p.setClipRect(r)
        area = QPainterPath(line)
        area.lineTo(pts[-1].x(), r.bottom())
        area.lineTo(pts[0].x(), r.bottom())
        area.closeSubpath()
        g = QLinearGradient(0, r.top(), 0, r.bottom())
        g.setColorAt(0, qc(self.color_key, 110 if UK.is_dark() else 70))
        g.setColorAt(1, qc(self.color_key, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawPath(area)
        pen = QPen(QColor(T[self.color_key]), 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line)
        last = pts[-1]
        if last.x() <= r.right() + 0.5:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(self.color_key, 70))
            p.drawEllipse(last, 6, 6)
            p.setBrush(QColor(T[self.color_key]))
            p.drawEllipse(last, 3, 3)


# ───────────────────────── оцінка: стовпчики й радар ─────────────────────────
class ScoreBars(QWidget):
    """Сходинки від 0 до 100: світяться до оцінки (синій → м'ятний), заповнюються хвилею."""

    def __init__(self, bars: int = 44, height: int = 92):
        super().__init__()
        self.setMinimumHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.bars = bars
        self.v = 0.0
        self.anim = Anim(self, self._set, 1300, OUT)

    def _set(self, v):
        self.v = v
        self.update()

    def set_value(self, frac: float) -> None:
        self.anim.to(max(0.0, min(1.0, frac)), 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0, 0, 0, -16)
        n = self.bars
        gap = 3.0
        bw = (r.width() - gap * (n - 1)) / n
        lit = self.v * n
        good = self.v >= 0.8
        c0, c1 = QColor(T["acc"]), QColor(T["ok"] if good else T["cyan"])
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(n):
            h = r.height() * (0.12 + 0.88 * (i + 1) / n)
            x = r.left() + i * (bw + gap)
            rect = QRectF(x, r.bottom() - h, bw, h)
            if i < lit:
                col = mix(c0, c1, i / max(1, n - 1))
                col.setAlpha(int(255 * min(1.0, 0.4 + (lit - i))))
            else:
                col = QColor(T["line"])
            p.setBrush(col)
            p.drawRoundedRect(rect, min(2.0, bw / 2), min(2.0, bw / 2))
        p.setPen(QColor(T["mute"]))
        p.setFont(make_font(10))
        for k, lab in ((0, "0"), (0.5, "50"), (1.0, "100")):
            x = r.left() + (r.width() - 24) * k
            p.drawText(QRectF(x, r.bottom() + 3, 24, 13),
                       Qt.AlignmentFlag.AlignLeft if k == 0 else Qt.AlignmentFlag.AlignCenter if k == 0.5
                       else Qt.AlignmentFlag.AlignRight, lab)


class Radar(QWidget):
    """Радар оцінки: осі — складові, багатокутник — ваш ПК. axes: [(підпис, частка 0…1)]."""

    def __init__(self, size: int = 220):
        super().__init__()
        self.setMinimumSize(size, size)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.axes = []
        self.t = 0.0
        self.anim = Anim(self, self._set, 1000, QEasingCurve.Type.OutBack)

    def _set(self, t):
        self.t = t
        self.update()

    def set_axes(self, axes) -> None:
        self.axes = list(axes)
        self.anim.to(1.0, 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self.axes)
        if n < 3:
            return
        c = QPointF(self.width() / 2, self.height() / 2 + 4)
        rad = min(self.width() / 2 - 64, self.height() / 2 - 24)

        def pt(i, k):
            a = -math.pi / 2 + 2 * math.pi * i / n
            return QPointF(c.x() + rad * k * math.cos(a), c.y() + rad * k * math.sin(a))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for ring in (0.25, 0.5, 0.75, 1.0):
            path = QPainterPath(pt(0, ring))
            for i in range(1, n):
                path.lineTo(pt(i, ring))
            path.closeSubpath()
            p.setPen(QPen(QColor(T["line2"] if ring == 1.0 else T["line"]), 1))
            p.drawPath(path)
        for i in range(n):
            p.setPen(QPen(QColor(T["line"]), 1))
            p.drawLine(c, pt(i, 1.0))
        shape = QPainterPath()
        for i, (_, v) in enumerate(self.axes):
            q = pt(i, max(0.04, min(1.0, v)) * self.t)
            shape.moveTo(q) if i == 0 else shape.lineTo(q)
        shape.closeSubpath()
        g = QRadialGradient(c, rad)
        g.setColorAt(0, qc("acc", 60))
        g.setColorAt(1, qc("acc", 150 if UK.is_dark() else 110))
        p.setBrush(g)
        p.setPen(QPen(QColor(T["acc"]), 1.8))
        p.drawPath(shape)
        p.setPen(Qt.PenStyle.NoPen)
        for i, (_, v) in enumerate(self.axes):
            q = pt(i, max(0.04, min(1.0, v)) * self.t)
            p.setBrush(QColor(T["acc_h"] if UK.is_dark() else T["acc"]))
            p.drawEllipse(q, 3, 3)
        p.setFont(make_font(11))
        for i, (lab, v) in enumerate(self.axes):
            q = pt(i, 1.0)
            a = -math.pi / 2 + 2 * math.pi * i / n
            dx, dy = math.cos(a), math.sin(a)
            box = QRectF(q.x() - 60 + dx * 44, q.y() - 9 + dy * 14, 120, 18)
            p.setPen(QColor(T["sub"]))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, lab)


# ───────────────────────── галочка успіху ─────────────────────────
class CheckBurst(QWidget):
    """Коло, що наповнюється, і галочка, що малюється штрихом, — плюс короткий спалах."""

    def __init__(self, size: int = 64, color_key: str = "ok"):
        super().__init__()
        self.setFixedSize(size, size)
        self.color_key = color_key
        self.t = 0.0
        self.anim = Anim(self, self._set, 800, OUT)

    def _set(self, t):
        self.t = t
        self.update()

    def play(self) -> None:
        self.anim.to(1.0, 0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.width()
        c = QPointF(s / 2, s / 2)
        col = QColor(T[self.color_key])
        t = self.t
        # спалах
        if 0.2 < t < 1.0:
            k = (t - 0.2) / 0.8
            p.setPen(QPen(qc(self.color_key, int(160 * (1 - k))), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, s * 0.3 + s * 0.2 * k, s * 0.3 + s * 0.2 * k)
        a = min(1.0, t / 0.45)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(self.color_key, int(60 * a)))
        p.drawEllipse(c, s * 0.42 * a, s * 0.42 * a)
        p.setBrush(col)
        p.drawEllipse(c, s * 0.3 * a, s * 0.3 * a)
        k = max(0.0, min(1.0, (t - 0.35) / 0.5))
        if k > 0:
            path = QPainterPath(QPointF(s * 0.37, s * 0.51))
            path.lineTo(QPointF(s * 0.46, s * 0.6))
            path.lineTo(QPointF(s * 0.64, s * 0.41))
            pen = QPen(QColor(T["bg"] if UK.is_dark() else "#FFFFFF"), s * 0.055)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            total = path.length()
            pen.setDashPattern([total * k / pen.widthF(), 1000])
            p.setPen(pen)
            p.drawPath(path)


class Spinner(QWidget):
    """Маленьке кільце очікування."""

    def __init__(self, size: int = 18, color_key: str = "acc"):
        super().__init__()
        self.setFixedSize(size, size)
        self.color_key = color_key
        self.a = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

    def start(self):
        self.timer.start(16)
        self.show()

    def stop(self):
        self.timer.stop()

    def _tick(self):
        self.a = (self.a + 7) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(QPen(QColor(T["line2"]), 2))
        p.drawEllipse(r)
        g = QConicalGradient(r.center(), -self.a)
        g.setColorAt(0, QColor(T[self.color_key]))
        g.setColorAt(0.7, qc(self.color_key, 0))
        pen = QPen(g, 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(r, int(-self.a * 16), 270 * 16)


# ───────────────────────── картки головної ─────────────────────────
class ActionTile(QAbstractButton):
    """Швидка дія: іконка в кольоровому квадраті, назва, пояснення; при наведенні — підсвітка й підйом."""

    def __init__(self, icon: str, title: str, desc: str, color_key: str = "acc"):
        super().__init__()
        self.icon_name, self.title, self.desc, self.color_key = icon, title, desc, color_key
        self.badge = ""
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setMinimumHeight(70)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.hov = 0.0
        self._ha = Anim(self, self._set, 200)

    def setText(self, text):  # для доступності й тестів: text() — назва
        super().setText(text)

    def set_badge(self, text: str) -> None:
        self.badge = text
        self.update()

    def _set(self, v):
        self.hov = v
        self.update()

    def enterEvent(self, e):
        self._ha.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._ha.to(0.0)
        super().leaveEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.hov
        r = QRectF(self.rect()).adjusted(1, 2 - 2 * h, -1, -1 - 2 * h)
        p.setPen(QPen(mix(QColor(T["line"]), QColor(T[self.color_key]), 0.55 * h), 1))
        p.setBrush(mix(QColor(T["surf"]), QColor(T["surf2"]), h))
        p.drawRoundedRect(r, 14, 14)
        if h > 0.01:
            g = QRadialGradient(QPointF(r.left() + 34, r.center().y()), 90)
            g.setColorAt(0, qc(self.color_key, int(46 * h)))
            g.setColorAt(1, qc(self.color_key, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(r, 14, 14)
        box = QRectF(r.left() + 14, r.center().y() - 19, 38, 38)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(self.color_key, 40 if UK.is_dark() else 30))
        p.drawRoundedRect(box, 11, 11)
        p.drawPixmap(QPointF(box.center().x() - 10, box.center().y() - 10),
                     icon_pixmap(self.icon_name, T[self.color_key], 20))
        x = box.right() + 14
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(14, QFont.Weight.DemiBold))
        p.drawText(QRectF(x, r.top() + 13, r.width() - x - 16, 20), Qt.AlignmentFlag.AlignVCenter, self.title)
        p.setPen(QColor(T["sub"]))
        p.setFont(make_font(12))
        fm = p.fontMetrics()
        p.drawText(QRectF(x, r.top() + 34, r.width() - x - 16, 18), Qt.AlignmentFlag.AlignVCenter,
                   fm.elidedText(self.desc, Qt.TextElideMode.ElideRight, int(r.width() - x + r.left() - 16)))
        if self.badge:
            p.setFont(make_font(10, QFont.Weight.Bold))
            bw = p.fontMetrics().horizontalAdvance(self.badge) + 14
            br = QRectF(r.right() - bw - 10, r.top() + 10, bw, 18)
            p.setBrush(qc(self.color_key, 50))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(br, 9, 9)
            p.setPen(QColor(T[self.color_key]))
            p.drawText(br, Qt.AlignmentFlag.AlignCenter, self.badge)
        if self.hasFocus():
            p.setPen(QPen(QColor(T["acc_h"]), 1.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(r.adjusted(0.7, 0.7, -0.7, -0.7), 14, 14)


class MetricTile(QFrame):
    """Живий показник: іконка й назва, число з одиницею, підпис і графік за останні хвилини."""

    def __init__(self, icon: str, caption: str, color_key: str = "acc", unit: str = "%", n: int = 40):
        super().__init__()
        self.setObjectName("card")
        self.icon_name, self.caption, self.color_key, self.unit = icon, caption, color_key, unit
        self.setMinimumHeight(118)
        v = vbox(self, (16, 14, 16, 10), 4)
        top = hbox(spacing=8)
        self.ico = QLabel()
        self.ico.setFixedSize(24, 24)
        top.addWidget(self.ico)
        cap = QLabel(caption)
        cap.setObjectName("h3")
        top.addWidget(cap, 1)
        self.num = CountLabel(lambda v: f"{v:.0f}", ms=700)
        self.num.setStyleSheet("font-size: 22px; font-weight: 700;")
        top.addWidget(self.num)
        self.unit_lbl = QLabel(unit)
        self.unit_lbl.setObjectName("muted")
        top.addWidget(self.unit_lbl, 0, Qt.AlignmentFlag.AlignBottom)
        v.addLayout(top)
        self.detail = QLabel("")
        self.detail.setObjectName("desc")
        v.addWidget(self.detail)
        self.graph = LiveGraph(n, 40, color_key, grid=False)
        v.addWidget(self.graph, 1)
        self.retheme()

    def retheme(self):
        self.ico.setPixmap(icon_pixmap(self.icon_name, T[self.color_key], 20))
        self.graph.color_key = self.color_key

    def set_color(self, key: str) -> None:
        if key != self.color_key:
            self.color_key = key
            self.retheme()

    def push(self, value: float, frac: float = None, text: str = None) -> None:
        """value — число на картці; frac — висота на графіку (0…1)."""
        self.num.set_value(value)
        self.graph.push(value / 100 if frac is None else frac)
        if text is not None:
            self.detail.setText(text)


# ───────────────────────── вибір теми в налаштуваннях ─────────────────────────
class ThemeCard(QAbstractButton):
    """Картка теми з мініатюрою вікна в її кольорах. name: system | dark | light."""

    def __init__(self, name: str, title: str):
        super().__init__()
        self.name, self.title = name, title
        self.setText(title)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setFixedHeight(132)
        self.setMinimumWidth(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.hov = 0.0
        self._ha = Anim(self, self._set, 160)

    def _set(self, v):
        self.hov = v
        self.update()

    def enterEvent(self, e):
        self._ha.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._ha.to(0.0)
        super().leaveEvent(e)

    @staticmethod
    def _mini(p: QPainter, r: QRectF, pal: dict) -> None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(pal["bg"]))
        p.drawRoundedRect(r, 8, 8)
        side = QRectF(r.left(), r.top(), r.width() * 0.22, r.height())
        p.setBrush(QColor(pal["side"]))
        p.drawRoundedRect(side, 8, 8)
        p.drawRect(QRectF(side.right() - 8, side.top(), 8, side.height()))
        for i in range(4):
            p.setBrush(QColor(pal["acc"] if i == 0 else pal["line2"]))
            p.drawRoundedRect(QRectF(side.left() + 6, side.top() + 10 + i * 11, side.width() - 12, 5), 2.5, 2.5)
        x0 = side.right() + 8
        hero = QRectF(x0, r.top() + 9, r.right() - x0 - 8, r.height() * 0.42)
        g = QLinearGradient(hero.topLeft(), hero.bottomRight())
        g.setColorAt(0, QColor(pal["acc_bg"]))
        g.setColorAt(1, QColor(pal["surf"]))
        p.setBrush(g)
        p.drawRoundedRect(hero, 5, 5)
        n = 12
        bw = (hero.width() * 0.55) / n
        for i in range(n):
            h = (hero.height() - 12) * (0.2 + 0.8 * (i + 1) / n)
            c = mix(QColor(pal["acc"]), QColor(pal["ok"]), i / n)
            p.setBrush(c)
            p.drawRect(QRectF(hero.left() + 8 + i * bw, hero.bottom() - 6 - h, bw - 1.2, h))
        y = hero.bottom() + 6
        tw = (r.right() - x0 - 8 - 12) / 3
        for i in range(3):
            p.setBrush(QColor(pal["surf"]))
            p.drawRoundedRect(QRectF(x0 + i * (tw + 6), y, tw, r.bottom() - y - 8), 4, 4)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        p.setPen(QPen(QColor(T["acc"]) if on else mix(QColor(T["line"]), QColor(T["line3"]), self.hov),
                      2 if on else 1))
        p.setBrush(QColor(T["surf"]))
        p.drawRoundedRect(r, 14, 14)
        prev = QRectF(r.left() + 10, r.top() + 10, r.width() - 20, r.height() - 46)
        if self.name == "system":
            p.save()
            clip = QPainterPath()
            clip.moveTo(prev.topLeft())
            clip.lineTo(prev.topRight())
            clip.lineTo(prev.bottomLeft())
            clip.closeSubpath()
            p.setClipPath(clip)
            self._mini(p, prev, UK.THEMES["dark"])
            p.restore()
            p.save()
            clip = QPainterPath()
            clip.moveTo(prev.topRight())
            clip.lineTo(prev.bottomRight())
            clip.lineTo(prev.bottomLeft())
            clip.closeSubpath()
            p.setClipPath(clip)
            self._mini(p, prev, UK.THEMES["light"])
            p.restore()
        else:
            self._mini(p, prev, UK.THEMES[self.name])
        p.setPen(QPen(QColor(T["line"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(prev, 8, 8)
        cy = r.bottom() - 18
        p.setPen(QPen(QColor(T["acc"]) if on else QColor(T["line3"]), 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(r.left() + 20, cy), 7, 7)
        if on:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T["acc"]))
            p.drawEllipse(QPointF(r.left() + 20, cy), 4, 4)
        p.setPen(QColor(T["text"]))
        p.setFont(make_font(13, QFont.Weight.DemiBold if on else QFont.Weight.Normal))
        p.drawText(QRectF(r.left() + 34, cy - 10, r.width() - 40, 20), Qt.AlignmentFlag.AlignVCenter, self.title)
