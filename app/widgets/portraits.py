"""Load fictional candidate portraits as circular pixmaps with a painted fallback."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel

from app.core.utils import asset_path

FALLBACK = {
    "CAN-D01": ("#155E75", "#A5F3FC", "AS"),
    "CAN-D02": ("#14532D", "#6EE7B7", "RP"),
    "CAN-D03": ("#78350F", "#FDE68A", "NB"),
    "CAN-D04": ("#4C1D95", "#DDD6FE", "FO"),
}


def _paint_fallback(candidate_id: str, size: int) -> QPixmap:
    bg, fg, initials = FALLBACK.get(candidate_id, ("#1B2940", "#94A3B8", "?"))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(bg))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(1, 1, size - 2, size - 2)
    painter.setBrush(QColor(fg))
    painter.drawEllipse(QRectF(size * 0.32, size * 0.18, size * 0.36, size * 0.36))
    painter.setPen(QColor("#0B1120"))
    painter.setFont(QFont("Segoe UI", max(8, size // 5), QFont.Weight.Bold))
    painter.drawText(QRectF(0, size * 0.22, size, size * 0.4), Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return pixmap


def _load_portrait(path, size: int) -> QPixmap:
    if not path.exists():
        return QPixmap()
    if path.suffix.lower() == ".svg":
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QPixmap()
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return pixmap
    return QPixmap(str(path))


def candidate_portrait_pixmap(record: dict, size: int = 48) -> QPixmap:
    relative = record.get("portrait_path") or f"images/candidates/{record.get('portrait_file', '')}"
    path = asset_path(*relative.split("/"))
    source = _load_portrait(path, size)
    if source.isNull():
        source = _paint_fallback(record.get("candidate_id", ""), size)
    else:
        source = source.scaled(
            size,
            size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = max(0, (source.width() - size) // 2)
        top = max(0, (source.height() - size) // 2)
        source = source.copy(left, top, size, size)

    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(QRectF(1, 1, size - 2, size - 2))
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, source)
    painter.setClipping(False)
    painter.setPen(QColor(record.get("accent", "#22D3EE")))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    painter.end()
    return result


class PortraitLabel(QLabel):
    def __init__(self, record: dict, size: int = 48, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border: none;")
        self.setPixmap(candidate_portrait_pixmap(record, size))
        self.setToolTip(f"{record.get('candidate_name')} (fictional demo portrait)")
