"""Radial action menu that pops up around the pet while the cursor is on it."""

from __future__ import annotations

import math

from PyQt6.QtCore import QPoint, QPointF, QPropertyAnimation, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QRegion,
)
from PyQt6.QtWidgets import QWidget

SIZE = 300
R_OUT = 148.0
R_IN = 104.0
GAP_DEG = 3.0

ACTIONS = ("吃饭", "睡觉", "挥手", "喝水")

FILL = QColor(212, 209, 218, 170)
FILL_HOVER = QColor(247, 172, 204, 225)
BORDER = QColor(255, 255, 255, 150)
TEXT = QColor(58, 50, 64)


class ActionWheel(QWidget):
    hover_entered = pyqtSignal()
    hover_left = pyqtSignal()
    action_triggered = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.resize(SIZE, SIZE)

        self._hover = -1
        self._paths = self._build_paths()
        self.setMask(self._build_mask())

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(140)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(0.96)

    # ------------------------------------------------------------- geometry

    def _build_paths(self) -> list[QPainterPath]:
        center = QPointF(SIZE / 2, SIZE / 2)
        outer = QRectF(
            center.x() - R_OUT, center.y() - R_OUT, 2 * R_OUT, 2 * R_OUT
        )
        inner = QRectF(center.x() - R_IN, center.y() - R_IN, 2 * R_IN, 2 * R_IN)

        paths = []
        for index in range(len(ACTIONS)):
            start = 135.0 - 90.0 * index + GAP_DEG / 2
            sweep = -90.0 + GAP_DEG
            path = QPainterPath()
            path.arcMoveTo(outer, start)
            path.arcTo(outer, start, sweep)
            path.arcTo(inner, start + sweep, -sweep)
            path.closeSubpath()
            paths.append(path)
        return paths

    def _build_mask(self) -> QRegion:
        region = QRegion()
        for path in self._paths:
            region += QRegion(path.toFillPolygon().toPolygon())
        return region

    def hover_index(self) -> int:
        return self._hover

    def index_at(self, pos: QPointF) -> int:
        for index, path in enumerate(self._paths):
            if path.contains(pos):
                return index
        return -1

    # ---------------------------------------------------------------- show

    def show_for(self, center: QPoint) -> None:
        screen = QGuiApplication.screenAt(center) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        x = min(
            max(center.x() - SIZE // 2, avail.left() - 6),
            avail.right() - SIZE + 6,
        )
        y = min(
            max(center.y() - SIZE // 2, avail.top() - 6),
            avail.bottom() - SIZE + 6,
        )
        self._hover = -1
        self.move(x, y)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self._fade.stop()
        self._fade.start()
        self.update()

    def hide_wheel(self) -> None:
        self._hover = -1
        self.hide()

    # --------------------------------------------------------------- events

    def enterEvent(self, event) -> None:
        self.hover_entered.emit()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.update()
        self.hover_left.emit()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event) -> None:
        index = self.index_at(event.position())
        if index != self._hover:
            self._hover = index
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        index = self.index_at(event.position())
        if index >= 0:
            action = ACTIONS[index]
            self._hover = -1
            self.update()
            self.action_triggered.emit(action)

    # ---------------------------------------------------------------- paint

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for index, path in enumerate(self._paths):
            painter.setPen(QPen(BORDER, 1.5))
            painter.setBrush(FILL_HOVER if index == self._hover else FILL)
            painter.drawPath(path)

        font = QFont("Microsoft YaHei UI", 11)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.setPen(TEXT)

        mid = (R_IN + R_OUT) / 2
        for index, label in enumerate(ACTIONS):
            angle = math.radians(90 - 90 * index)
            cx = SIZE / 2 + mid * math.cos(angle)
            cy = SIZE / 2 - mid * math.sin(angle)
            painter.drawText(
                QRectF(cx - 44, cy - 14, 88, 28),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )
