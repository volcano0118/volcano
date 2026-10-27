"""Kuromi desktop-pet sprite renderer (Qt vector drawing).

Everything is drawn with QPainterPath at any scale, so the sprite stays crisp at
any size or display scaling. No image assets are needed.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)

CANVAS_W, CANVAS_H = 200, 250

INK = QColor("#2c2531")
HOOD = QColor("#4c4653")
WHITE = QColor("#fcfbfd")
SKULL = QColor("#ef92a6")
PINK = QColor("#f4a0c2")
TONGUE = QColor("#e8748f")
EYE = QColor("#1d1922")

IDLE_DY = [0, 0, 1, 1, 2, 1]
WAVE_STEPS = 8


def _pen(color=INK, width=2.0):
    pen = QPen(color)
    pen.setWidthF(width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _fill(p, path, color, outline=None, width=2.0):
    p.setPen(_pen(outline, width) if outline is not None else Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(path)


def _curve(points):
    path = QPainterPath(QPointF(*points[0]))
    i = 1
    while i < len(points):
        if i + 2 < len(points):
            path.cubicTo(
                QPointF(*points[i]), QPointF(*points[i + 1]), QPointF(*points[i + 2])
            )
            i += 3
        else:
            path.lineTo(QPointF(*points[i]))
            i += 1
    return path


def _limb(p, points, width, color=WHITE, outline=INK, ow=2.0):
    path = _curve(points)
    p.strokePath(path, _pen(outline, width + 2 * ow))
    p.strokePath(path, _pen(color, width))


def _draw_tail(p):
    tail = _curve([(122, 202), (146, 210), (159, 204), (163, 196)])
    p.strokePath(tail, _pen(INK, 8.5))
    p.strokePath(tail, _pen(HOOD, 4.8))
    spade = QPainterPath(QPointF(160, 199))
    spade.quadTo(QPointF(168, 188), QPointF(174, 182))
    spade.quadTo(QPointF(168, 182), QPointF(155, 188))
    spade.closeSubpath()
    _fill(p, spade, HOOD, INK, 1.6)


def _leg_path(cx, lift):
    leg = QPainterPath(QPointF(cx - 15, 196 - lift))
    leg.cubicTo(
        QPointF(cx - 15, 212 - lift),
        QPointF(cx - 14, 220 - lift),
        QPointF(cx - 12, 226 - lift),
    )
    leg.lineTo(cx + 12, 226 - lift)
    leg.cubicTo(
        QPointF(cx + 14, 220 - lift),
        QPointF(cx + 15, 212 - lift),
        QPointF(cx + 15, 196 - lift),
    )
    leg.closeSubpath()
    return leg


def _draw_body(p, walk=None):
    shape = QPainterPath()
    shape.addEllipse(QRectF(58, 146, 84, 68))
    for cx, offset in ((82, 0.0), (118, 0.5)):
        lift = 0.0
        shift = 0.0
        if walk is not None:
            phase = walk + offset
            lift = max(0.0, -math.sin(2 * math.pi * phase)) * 5.0
            shift = math.cos(2 * math.pi * phase) * 6.0
        shape = shape.united(_leg_path(cx + shift, lift))
        foot = QPainterPath()
        foot.addEllipse(QRectF(cx + shift - 17, 220 - lift, 34, 25))
        shape = shape.united(foot)
    _fill(p, shape, WHITE, INK, 2.4)


def _draw_collar(p):
    collar = QPainterPath(QPointF(60, 148))
    collar.lineTo(140, 148)
    collar.lineTo(154, 168)
    collar.lineTo(126, 178)
    collar.lineTo(118, 158)
    collar.quadTo(QPointF(114, 178), QPointF(100, 182))
    collar.quadTo(QPointF(86, 178), QPointF(82, 158))
    collar.lineTo(74, 178)
    collar.lineTo(46, 168)
    collar.closeSubpath()
    _fill(p, collar, HOOD, INK, 2.2)
    for cx, cy, r in ((46, 168, 7), (154, 168, 7), (76, 174, 6), (124, 174, 6)):
        ball = QPainterPath()
        ball.addEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        _fill(p, ball, PINK, INK, 1.6)


def _draw_arm(p, shoulder, control, paw, width=14.0, hand_size=8.5):
    line = _curve([shoulder, control, paw])
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    shape = stroker.createStroke(line)
    hand = QPainterPath()
    hand.addEllipse(
        QRectF(paw[0] - hand_size, paw[1] - hand_size, hand_size * 2, hand_size * 2)
    )
    shape = shape.united(hand)
    _fill(p, shape, WHITE, INK, 2.0)


def _wave_arm(p, phase):
    sway = 5.0 * math.sin(2 * math.pi * phase)
    paw = (150 + sway, 140 - abs(sway) * 0.35)
    _draw_arm(p, (130, 180), (147 + sway * 0.4, 160), paw, 14.0)


def _ear(tip, base_in, base_out, bend):
    path = QPainterPath(QPointF(*base_in))
    path.quadTo(QPointF(bend[0], bend[1]), QPointF(*tip))
    path.quadTo(QPointF(bend[2], bend[3]), QPointF(*base_out))
    path.closeSubpath()
    return path


def _draw_head(p, blink, mouth_open=0.0):
    ears = [
        _ear((30, 14), (84, 44), (42, 72), (44, 24, 34, 60)),
        _ear((170, 14), (116, 44), (158, 72), (156, 24, 166, 60)),
    ]
    for ear in ears:
        _fill(p, ear, HOOD, INK, 2.2)
    for cx in (30, 170):
        ball = QPainterPath()
        ball.addEllipse(QRectF(cx - 9, 5, 18, 18))
        _fill(p, ball, HOOD, INK, 2.2)

    hood = QPainterPath()
    hood.addEllipse(QRectF(30, 44, 140, 126))
    _fill(p, hood, HOOD, INK, 2.2)

    face = QPainterPath()
    face.addEllipse(QRectF(41, 84, 118, 82))
    _fill(p, face, WHITE, INK, 2.2)

    hairline = QPainterPath(QPointF(39, 72))
    hairline.lineTo(39, 112)
    hairline.cubicTo(QPointF(39, 96), QPointF(51, 87), QPointF(66, 87))
    hairline.lineTo(100, 106)
    hairline.lineTo(134, 87)
    hairline.cubicTo(QPointF(149, 87), QPointF(161, 96), QPointF(161, 112))
    hairline.lineTo(161, 72)
    hairline.closeSubpath()
    _fill(p, hairline, HOOD)

    _draw_skull(p)
    _draw_eyes(p, blink)
    _draw_nose(p)
    _draw_mouth(p, mouth_open)


def _draw_skull(p):
    cranium = QPainterPath()
    cranium.addEllipse(QRectF(81, 44, 38, 30))
    jaw = QPainterPath()
    jaw.addRect(QRectF(91, 71, 18, 7))
    _fill(p, cranium.united(jaw), SKULL, INK, 1.6)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(INK)
    for cx in (90, 103):
        eye = QPainterPath()
        eye.addEllipse(QRectF(cx, 54, 7, 8))
        p.drawPath(eye)
    p.setPen(_pen(INK, 1.4))
    for x in (97, 103):
        p.drawLine(QPointF(x, 72), QPointF(x, 77.5))


def _eye_path():
    path = QPainterPath(QPointF(65, 114))
    path.cubicTo(QPointF(70, 118), QPointF(80, 118), QPointF(84, 114))
    path.cubicTo(QPointF(85, 124), QPointF(82, 135), QPointF(74, 135))
    path.cubicTo(QPointF(67, 135), QPointF(64, 124), QPointF(65, 114))
    path.closeSubpath()
    return path


def _draw_one_eye(p, blink):
    p.save()
    p.translate(-9, 0)
    p.translate(74.5, 124.5)
    p.rotate(14)
    p.translate(-74.5, -124.5)
    if blink:
        lid = QPainterPath(QPointF(66, 119))
        lid.cubicTo(QPointF(71, 123), QPointF(79, 123), QPointF(83, 119))
        p.strokePath(lid, _pen(INK, 3.2))
    else:
        _fill(p, _eye_path(), EYE)
        for k in (0, 1):
            lash = QPainterPath(QPointF(66, 114 + k * 2.5))
            lash.lineTo(QPointF(57, 112 + k * 2.5))
            p.strokePath(lash, _pen(INK, 2.2))
    p.restore()


def _draw_eyes(p, blink):
    _draw_one_eye(p, blink)
    p.save()
    p.translate(CANVAS_W, 0)
    p.scale(-1, 1)
    _draw_one_eye(p, blink)
    p.restore()


def _draw_nose(p):
    nose = QPainterPath()
    nose.addEllipse(QRectF(95, 139, 10, 9))
    _fill(p, nose, SKULL, INK, 1.5)


def _draw_mouth(p, open_amount=0.0):
    if open_amount > 0.12:
        height = 4.0 + 6.0 * min(1.0, open_amount)
        mouth = QPainterPath()
        mouth.addEllipse(QRectF(94.5, 149.5, 11, height))
        _fill(p, mouth, QColor("#e8748f"), INK, 1.5)
        return
    mouth = QPainterPath(QPointF(92, 151))
    mouth.cubicTo(QPointF(96, 158), QPointF(104, 158), QPointF(108, 151))
    p.strokePath(mouth, _pen(INK, 2.0))


def _draw_bowl(p, phase):
    lift = 12.0 * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
    top = 180.0 - lift

    bowl = QPainterPath(QPointF(76, top))
    bowl.quadTo(QPointF(78, top + 20), QPointF(100, top + 20))
    bowl.quadTo(QPointF(122, top + 20), QPointF(124, top))
    bowl.closeSubpath()
    _fill(p, bowl, QColor(252, 232, 240), INK, 2.0)

    rice = QPainterPath()
    rice.moveTo(82, top - 2)
    rice.quadTo(QPointF(100, top - 18), QPointF(118, top - 2))
    rice.closeSubpath()
    _fill(p, rice, WHITE, INK, 1.5)

    rim = QPainterPath()
    rim.addEllipse(QRectF(74, top - 5, 52, 11))
    _fill(p, rim, PINK, INK, 1.8)


def _draw_cup(p, phase):
    lift = 10.0 * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
    cx = 100.0
    top = 170.0 - lift

    glass = QPainterPath()
    glass.addRoundedRect(QRectF(cx - 10, top - 18, 20, 30), 5, 5)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 205))
    p.drawPath(glass)

    p.save()
    p.setClipPath(glass)
    level = 17.0 * (1.0 - 0.55 * phase)
    p.fillRect(
        QRectF(cx - 10, top + 12 - level, 20, level),
        QColor(140, 200, 232, 235),
    )
    p.restore()

    p.setPen(_pen(INK, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(glass)


def _draw_zzz(p, phase):
    for index in range(3):
        t = (phase + index / 3.0) % 1.0
        alpha = int(210 * (1.0 - t))
        if alpha <= 6:
            continue
        font = QFont("Segoe UI", int(11 + 9 * t))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(74, 66, 82, alpha))
        p.drawText(QPointF(162 + 24 * t, 102 - 54 * t), "Z")


def render(dy=0, blink=False, wave=None, scale=1.0, walk=None, action=None, phase=0.0):
    img = QImage(
        max(1, round(CANVAS_W * scale)),
        max(1, round(CANVAS_H * scale)),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(scale, scale)
    bob = 0.0
    mouth_open = 0.0
    if walk is not None:
        bob = 1.6 * (1 - math.cos(4 * math.pi * walk)) / 2
    if action == "eat":
        chew = max(0.0, math.sin(2 * math.pi * phase))
        mouth_open = chew
        bob = 2.2 * chew
    elif action == "drink":
        mouth_open = 0.45 + 0.45 * math.sin(2 * math.pi * phase)
    elif action == "sleep":
        blink = True
        bob = 0.7 * (1 - math.cos(2 * math.pi * phase))
    p.translate(0, dy - bob)

    _draw_tail(p)
    _draw_body(p, walk)
    _draw_collar(p)
    _draw_head(p, blink, mouth_open)
    if action == "eat":
        _draw_bowl(p, phase)
    elif action == "drink":
        _draw_cup(p, phase)

    swing = 0.0 if walk is None else math.sin(2 * math.pi * walk) * 3.5
    if action in ("eat", "drink"):
        if action == "eat":
            paw_y = 180.0 - 12.0 * (0.5 - 0.5 * math.cos(2 * math.pi * phase)) - 2
            left_paw, right_paw = (77, paw_y), (123, paw_y)
        else:
            paw_y = 170.0 - 10.0 * (0.5 - 0.5 * math.cos(2 * math.pi * phase)) - 1
            left_paw, right_paw = (87, paw_y), (113, paw_y)
        _draw_arm(
            p, (67, 176), (63, paw_y + 8), left_paw,
            width=11.0, hand_size=7.0,
        )
        _draw_arm(
            p, (133, 176), (137, paw_y + 8), right_paw,
            width=11.0, hand_size=7.0,
        )
    else:
        _draw_arm(
            p, (67, 174), (60 + swing, 185), (61 + swing * 1.6, 196),
            width=12.0, hand_size=8.0,
        )
        if wave is None:
            _draw_arm(
                p, (133, 174), (140 - swing, 185), (139 - swing * 1.6, 196),
                width=12.0, hand_size=8.0,
            )
        else:
            _wave_arm(p, wave / WAVE_STEPS)

    if action == "sleep":
        _draw_zzz(p, phase)
    p.end()
    return img


def idle_frame(i, blink=False, scale=1.0):
    return render(IDLE_DY[i % len(IDLE_DY)], blink, None, scale)


def wave_frame(i, scale=1.0):
    return render(IDLE_DY[i % len(IDLE_DY)], False, i % WAVE_STEPS, scale)


def walk_frame(i, scale=1.0):
    steps = 8
    return render(0, False, None, scale, walk=(i % steps) / steps)


ACTION_STEPS = 8


def action_frame(name, i, scale=1.0):
    return render(
        0, False, None, scale, action=name, phase=(i % ACTION_STEPS) / ACTION_STEPS
    )


def frame_counts():
    return len(IDLE_DY), WAVE_STEPS


if __name__ == "__main__":
    import os
    import sys
    import tempfile

    from PyQt6.QtGui import QGuiApplication

    app = QGuiApplication(sys.argv)
    scale = 2.0
    sheet = QImage(
        round(CANVAS_W * scale * 2),
        round(CANVAS_H * scale * 2),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    sheet.fill(QColor("#b8d6e8"))
    sp = QPainter(sheet)
    tiles = [idle_frame(0), idle_frame(0, True), wave_frame(0), wave_frame(3)]
    for i, im in enumerate(tiles):
        sp.drawImage(
            round((i % 2) * CANVAS_W * scale),
            round((i // 2) * CANVAS_H * scale),
            im,
        )
    sp.end()
    out = os.path.join(tempfile.gettempdir(), "kuromi_preview.png")
    sheet.save(out)
    print(out)
