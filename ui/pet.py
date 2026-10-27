"""Kuromi desktop pet for Windows.

Behaviour
---------
* sits in place with a slow breathing bob and the occasional blink
* wanders around the desktop after 30 seconds without interaction
* waves at you while the cursor is over her
* drag her anywhere with the left mouse button
* double-click to open her window
* right-click for a small menu (wave / go back to the corner / quit)
"""

from __future__ import annotations

import math
import random
import time

from PyQt6.QtCore import QPoint, QSettings, Qt, QTimer
from PyQt6.QtGui import QCursor, QGuiApplication, QImage, QPainter, QPixmap, QRegion
from PyQt6.QtWidgets import QApplication, QMenu, QWidget

from character.art import (
    CANVAS_H,
    CANVAS_W,
    frame_counts,
    idle_frame,
    walk_frame,
    wave_frame,
)
from ui.chat import ChatWindow
from ui.wheel import ActionWheel

PET_SCALE = 0.55
PET_W = round(CANVAS_W * PET_SCALE)
PET_H = round(CANVAS_H * PET_SCALE)
DEVICE_DPR = 2
TICK_MS = 90
IDLE_TICKS_PER_FRAME = 2
BLINK_TICKS = 2
ALPHA_CUTOFF = 25
IDLE_WANDER_SECONDS = 30.0
WALK_SPEED = 70.0
WALK_TICK_MS = 25
WALK_MIN_DISTANCE = 130
WALK_STRIDE = 46.0
WALK_STEPS = 8


def _alpha_region(img: QImage) -> QRegion:
    """Clickable silhouette of a frame, in logical window coordinates."""
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = img.width(), img.height()
    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    data = bytes(ptr)
    stride = img.bytesPerLine()
    region = QRegion()
    for y in range(height):
        row = data[y * stride : (y + 1) * stride]
        x = 0
        while x < width:
            if row[x * 4 + 3] > ALPHA_CUTOFF:
                start = x
                while x < width and row[x * 4 + 3] > ALPHA_CUTOFF:
                    x += 1
                region += QRegion(start, y, x - start, 1)
            else:
                x += 1
    return region


class KuromiPet(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Kuromi")
        self.setMouseTracking(True)
        self.resize(PET_W, PET_H)

        self._idle_count, self._wave_count = frame_counts()
        self._frames: dict[tuple, tuple[QPixmap, QRegion]] = {}
        self._image: QPixmap | None = None
        self._mask: QRegion | None = None

        self._mode = "idle"
        self._idle_index = 0
        self._wave_index = 0
        self._ticks = 0
        self._blink_left = 0
        self._next_blink = random.randint(30, 70)
        self._hover = False
        self._greet_until = 16
        self._dragging = False
        self._drag_offset = QPoint()

        self._panel: ChatWindow | None = None
        self.last_action = ""
        self._wheel = ActionWheel()
        self._wheel.hover_entered.connect(self._cancel_wheel_hide)
        self._wheel.hover_left.connect(self._schedule_wheel_hide)
        self._wheel.action_triggered.connect(self._on_wheel_action)
        self._wheel_hide_timer = QTimer(self)
        self._wheel_hide_timer.setSingleShot(True)
        self._wheel_hide_timer.setInterval(420)
        self._wheel_hide_timer.timeout.connect(self._wheel_hide_if_idle)
        self._last_interaction = time.monotonic()
        self._walking = False
        self._walk_target = QPoint()
        self._walk_last = 0.0
        self._walk_done = 0.0
        self._walk_total = 1.0
        self._walk_phase = 0.0
        self._walk_frame = -1
        self._flip = False
        self._walk_timer = QTimer(self)
        self._walk_timer.timeout.connect(self._walk_step)

        self._settings = QSettings("KuromiPet", "KuromiPet")
        self._restore_position()
        self._show_frame(self._frame(blink=False))

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(TICK_MS)

    # ---------------------------------------------------------------- frames

    def _frame(
        self,
        blink: bool = False,
        wave: int | None = None,
        flip=False,
        walk: int | None = None,
    ):
        if walk is not None:
            key = ("walk", walk, flip)
        elif wave is not None:
            key = ("wave", wave, flip)
        else:
            key = ("idle", self._idle_index, blink, flip)
        cached = self._frames.get(key)
        if cached is not None:
            return cached

        if walk is not None:
            big = walk_frame(walk, scale=PET_SCALE * DEVICE_DPR)
            small = walk_frame(walk, scale=PET_SCALE)
        elif wave is not None:
            big = wave_frame(wave, scale=PET_SCALE * DEVICE_DPR)
            small = wave_frame(wave, scale=PET_SCALE)
        else:
            big = idle_frame(self._idle_index, blink, scale=PET_SCALE * DEVICE_DPR)
            small = idle_frame(self._idle_index, blink, scale=PET_SCALE)
        if flip:
            big = big.mirrored(True, False)
            small = small.mirrored(True, False)

        pixmap = QPixmap.fromImage(big)
        pixmap.setDevicePixelRatio(DEVICE_DPR)
        cached = (pixmap, _alpha_region(small))
        self._frames[key] = cached
        return cached

    def _show_frame(self, frame) -> None:
        self._image, self._mask = frame
        self.setMask(self._mask)
        self.update()

    # ----------------------------------------------------------------- state

    def _tick(self) -> None:
        self._ticks += 1
        self._maybe_wander()
        if self._walking:
            return
        if self._hover or self._ticks < self._greet_until:
            if self._mode != "wave":
                self._mode = "wave"
                self._wave_index = 0
            self._wave_index = (self._wave_index + 1) % self._wave_count
            self._show_frame(self._frame(wave=self._wave_index, flip=self._flip))
            return

        if self._mode != "idle":
            self._mode = "idle"
            self._show_frame(self._frame(blink=False, flip=self._flip))
        self._tick_idle()

    def _maybe_wander(self) -> None:
        if self._walking or self._hover or self._dragging:
            return
        if self._panel is not None and self._panel.isVisible():
            return
        if time.monotonic() - self._last_interaction >= IDLE_WANDER_SECONDS:
            self._start_walk()

    def _start_walk(self) -> None:
        rect = self.frameGeometry()
        screen = (
            QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        )
        avail = screen.availableGeometry()
        left = avail.left() + 8
        right = avail.right() - PET_W - 8
        top = avail.top() + 8
        bottom = avail.bottom() - PET_H - 8
        if right <= left or bottom <= top:
            self._note_interaction()
            return

        target = QPoint(self.x(), self.y())
        for _ in range(12):
            ty = min(max(self.y() + random.randint(-45, 45), top), bottom)
            candidate = QPoint(random.randint(left, right), ty)
            if (
                abs(candidate.x() - self.x()) + abs(candidate.y() - self.y())
                >= WALK_MIN_DISTANCE
            ):
                target = candidate
                break
        else:
            ty = min(max(self.y() + random.randint(-45, 45), top), bottom)
            target = QPoint(random.randint(left, right), ty)

        self._walking = True
        self._walk_target = target
        self._walk_last = time.monotonic()
        self._walk_done = 0.0
        self._walk_total = max(
            1.0, math.hypot(target.x() - self.x(), target.y() - self.y())
        )
        self._walk_phase = 0.0
        self._walk_frame = -1
        self._update_flip(target.x() - self.x())
        self._walk_timer.start(WALK_TICK_MS)

    def _update_flip(self, dx: float) -> None:
        if dx < -3:
            flip = True
        elif dx > 3:
            flip = False
        else:
            return
        if flip != self._flip:
            self._flip = flip
            self._show_frame(
                self._frame(blink=False, wave=None, flip=self._flip)
                if self._mode == "idle"
                else self._frame(
                    wave=self._wave_index, flip=self._flip
                )
            )

    def _walk_step(self) -> None:
        if self._hover or self._dragging:
            self._stop_walk()
            return

        now = time.monotonic()
        dt = now - self._walk_last
        self._walk_last = now

        pos = self.pos()
        dx = self._walk_target.x() - pos.x()
        dy = self._walk_target.y() - pos.y()
        dist = math.hypot(dx, dy)
        if dist < 1:
            self.move(self._walk_target)
            self._stop_walk()
            return

        ease = 0.35 + 0.65 * math.sin(
            math.pi * min(1.0, self._walk_done / self._walk_total)
        )
        step = min(dist, WALK_SPEED * dt * ease)
        self._walk_done += step

        self._update_flip(dx)
        self.move(
            round(pos.x() + dx / dist * step), round(pos.y() + dy / dist * step)
        )

        self._walk_phase = (self._walk_phase + step / WALK_STRIDE) % 1.0
        index = round(self._walk_phase * WALK_STEPS) % WALK_STEPS
        if index != self._walk_frame:
            self._walk_frame = index
            self._show_frame(self._frame(walk=index, flip=self._flip))

    def _stop_walk(self) -> None:
        self._wheel.hide_wheel()
        self._walk_timer.stop()
        self._walking = False
        self._mode = "idle"
        self._flip = False
        self._show_frame(self._frame(blink=False, flip=False))
        self._clamp_to_screen()
        self._settings.setValue("pos", self.frameGeometry().topLeft())
        self._note_interaction()

    def _note_interaction(self) -> None:
        self._last_interaction = time.monotonic()

    def _tick_idle(self) -> None:
        if self._blink_left > 0:
            self._blink_left -= 1
            self._show_frame(self._frame(blink=True, flip=self._flip))
            if self._blink_left == 0:
                self._next_blink = self._ticks + random.randint(30, 90)
            return
        if self._ticks >= self._next_blink:
            self._blink_left = BLINK_TICKS
            self._show_frame(self._frame(blink=True, flip=self._flip))
            return
        if self._ticks % IDLE_TICKS_PER_FRAME == 0:
            self._idle_index = (self._idle_index + 1) % self._idle_count
            self._show_frame(self._frame(blink=False, flip=self._flip))

    # ----------------------------------------------------------------- paint

    def paintEvent(self, event) -> None:
        if self._image is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self._image)

    # ----------------------------------------------------------------- mouse

    def enterEvent(self, event) -> None:
        self._hover = True
        self._note_interaction()
        self._cancel_wheel_hide()
        if not self._walking and not self._dragging:
            self._wheel.show_for(self.frameGeometry().center())
            self.raise_()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = False
        self._note_interaction()
        self._schedule_wheel_hide()
        super().leaveEvent(event)

    # ------------------------------------------------------------- action wheel

    def _cancel_wheel_hide(self) -> None:
        self._wheel_hide_timer.stop()

    def _schedule_wheel_hide(self) -> None:
        if self._wheel.isVisible():
            self._wheel_hide_timer.start()

    def _wheel_hide_if_idle(self) -> None:
        if self._hover:
            return
        if self._wheel.isVisible():
            local = self._wheel.mapFromGlobal(QCursor.pos())
            if self._wheel.index_at(local.toPointF()) >= 0:
                self._wheel_hide_timer.start()
                return
        self._wheel.hide_wheel()

    def _on_wheel_action(self, action: str) -> None:
        self.last_action = action
        self._wheel.hide_wheel()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._note_interaction()
            self._stop_walk()
            self._dragging = True
            self._wheel.hide_wheel()
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self._note_interaction()
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._note_interaction()
            self._stop_walk()
            self._wheel.hide_wheel()
            self._open_panel()
            event.accept()

    def _open_panel(self) -> None:
        if self._panel is None:
            self._panel = ChatWindow()
        self._panel.open()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._clamp_to_screen()
            self._note_interaction()
            self._settings.setValue("pos", self.frameGeometry().topLeft())
            event.accept()

    def contextMenuEvent(self, event) -> None:
        self._note_interaction()
        menu = QMenu(self)
        wave_action = menu.addAction("挥手打招呼")
        corner_action = menu.addAction("回到右下角")
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        menu.setStyleSheet(
            "QMenu { background: #2a242f; color: #f7accc; border: 1px solid #f7accc;"
            " padding: 4px; }"
            "QMenu::item { padding: 5px 18px; border-radius: 4px; }"
            "QMenu::item:selected { background: #f7accc; color: #2a242f; }"
        )
        chosen = menu.exec(event.globalPos())
        if chosen is wave_action:
            self._greet_until = self._ticks + 4 * self._wave_count
        elif chosen is corner_action:
            self._move_to_corner()
        elif chosen is quit_action:
            self._settings.setValue("pos", self.frameGeometry().topLeft())
            if self._panel is not None:
                self._panel.shutdown()
            QApplication.quit()

    # ------------------------------------------------------------- placement

    def _move_to_corner(self) -> None:
        avail = QGuiApplication.primaryScreen().availableGeometry()
        self.move(avail.right() - PET_W - 90, avail.bottom() - PET_H - 40)
        self._settings.setValue("pos", self.frameGeometry().topLeft())

    def _restore_position(self) -> None:
        saved = self._settings.value("pos")
        if isinstance(saved, QPoint):
            self.move(saved)
            if not self._visible_on_some_screen():
                self._move_to_corner()
        else:
            self._move_to_corner()

    def _visible_on_some_screen(self) -> bool:
        rect = self.frameGeometry()
        return any(
            screen.availableGeometry().intersects(rect)
            for screen in QGuiApplication.screens()
        )

    def _clamp_to_screen(self) -> None:
        rect = self.frameGeometry()
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        x = min(max(rect.left(), avail.left()), avail.right() - PET_W + 1)
        y = min(max(rect.top(), avail.top()), avail.bottom() - PET_H + 1)
        self.move(x, y)
