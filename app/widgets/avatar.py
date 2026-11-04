"""Circular officer photograph with a neutral fallback (no initials)."""

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from app.core.utils import asset_path

PROFILE_IMAGE = ("images", "sahira_profile.jpg")
BORDER = QColor("#22D3EE")
FILL = QColor("#1B2940")
MUTED = QColor("#94A3B8")


def profile_image_path():
    return asset_path(*PROFILE_IMAGE)


def circular_photo_pixmap(size: int = 40) -> QPixmap | None:
    path = profile_image_path()
    if not path.exists():
        return None
    source = QPixmap(str(path))
    if source.isNull() or source.width() < 8 or source.height() < 8:
        return None
    width, height = source.width(), source.height()
    side = min(width, height)
    x = max(0, (width - side) // 2)
    y = 0 if height >= width else max(0, (height - side) // 2)
    square = source.copy(x, y, side, side)
    scaled = square.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    if scaled.width() != size or scaled.height() != size:
        left = max(0, (scaled.width() - size) // 2)
        top = max(0, (scaled.height() - size) // 2)
        scaled = scaled.copy(left, top, size, size)

    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addEllipse(QRectF(1, 1, size - 2, size - 2))
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.setClipping(False)
    painter.setPen(BORDER)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    painter.end()
    return result


def placeholder_pixmap(size: int = 40) -> QPixmap:
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(FILL)
    painter.setPen(BORDER)
    painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    painter.setPen(MUTED)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    head = QRectF(size * 0.32, size * 0.18, size * 0.36, size * 0.36)
    painter.drawEllipse(head)
    body = QPainterPath()
    body.moveTo(size * 0.18, size * 0.86)
    body.quadTo(size * 0.50, size * 0.48, size * 0.82, size * 0.86)
    painter.drawPath(body)
    painter.end()
    return result


def officer_avatar_pixmap(size: int = 40) -> QPixmap:
    return circular_photo_pixmap(size) or placeholder_pixmap(size)


class AvatarLabel(QLabel):
    def __init__(self, size: int = 40, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)
        self.setPixmap(officer_avatar_pixmap(size))
        self.setToolTip("Sahira · Election Officer")
