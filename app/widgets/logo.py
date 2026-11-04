"""BallotVision brand mark: SVG asset with a painted fallback."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from app.core.utils import asset_path

NAVY = QColor("#0F172A")
CYAN = QColor("#22D3EE")
TEAL = QColor("#2DD4BF")
PAPER = QColor("#F8FAFC")
INK = QColor("#0F172A")
HEADER = QColor("#155E75")
MUTED = QColor("#94A3B8")
MARK = QColor("#0E7490")


def _paint_mark(painter: QPainter, rect: QRectF) -> None:
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = min(rect.width(), rect.height()) / 64.0
    painter.save()
    painter.translate(rect.x(), rect.y())
    painter.scale(scale, scale)

    bg = QPainterPath()
    bg.addRoundedRect(QRectF(0, 0, 64, 64), 14, 14)
    painter.fillPath(bg, NAVY)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(CYAN, 2.4))
    painter.drawEllipse(QRectF(5, 5, 54, 54))
    painter.setPen(QPen(TEAL, 1.2))
    painter.drawEllipse(QRectF(9.5, 9.5, 45, 45))

    paper = QPainterPath()
    paper.addRoundedRect(QRectF(18, 12, 28, 40), 3.5, 3.5)
    painter.fillPath(paper, PAPER)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(HEADER)
    painter.drawRect(QRectF(18, 16, 28, 4))
    header = QPainterPath()
    header.addRoundedRect(QRectF(18, 12, 28, 8), 3.5, 3.5)
    painter.fillPath(header, HEADER)
    painter.setBrush(HEADER)
    painter.drawRect(QRectF(18, 16, 28, 4))
    painter.setBrush(QColor("#A5F3FC"))
    painter.drawRoundedRect(QRectF(22, 14.2, 12, 2.2), 1, 1)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(INK, 1.6))
    painter.drawRoundedRect(QRectF(22, 24, 7, 7), 1.2, 1.2)
    painter.setPen(QPen(MARK, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(23.6, 27.4, 24.9, 28.8)
    painter.drawLine(24.9, 28.8, 27.7, 25.4)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(MUTED)
    painter.drawRoundedRect(QRectF(32, 25.6, 10, 2.2), 1, 1)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(INK, 1.6))
    painter.drawRoundedRect(QRectF(22, 35, 7, 7), 1.2, 1.2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(MUTED)
    painter.drawRoundedRect(QRectF(32, 36.6, 10, 2.2), 1, 1)
    painter.setBrush(QColor("#CBD5E1"))
    painter.drawRoundedRect(QRectF(22, 45.5, 7, 3.2), 1, 1)

    painter.setBrush(NAVY)
    painter.setPen(QPen(CYAN, 2))
    painter.drawEllipse(QRectF(36.5, 38.5, 15, 15))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(TEAL, 1.5))
    painter.drawEllipse(QRectF(40.8, 42.8, 6.4, 6.4))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(CYAN)
    painter.drawEllipse(QRectF(42.8, 44.8, 2.4, 2.4))
    painter.restore()


def logo_pixmap(size: int = 64) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    _paint_mark(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def logo_icon(size: int = 64) -> QIcon:
    ico = asset_path("ballotvision.ico")
    if ico.exists():
        icon = QIcon(str(ico))
        if not icon.isNull():
            return icon
    png = asset_path("ballotvision.png")
    if png.exists():
        icon = QIcon(str(png))
        if not icon.isNull():
            return icon
    svg = asset_path("ballotvision_logo.svg")
    if svg.exists():
        icon = QIcon(str(svg))
        if not icon.isNull():
            return icon
    icon = QIcon()
    icon.addPixmap(logo_pixmap(size))
    icon.addPixmap(logo_pixmap(32))
    icon.addPixmap(logo_pixmap(16))
    return icon


class LogoMark(QWidget):
    def __init__(self, size: int = 36, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._renderer = None
        svg = asset_path("ballotvision_logo.svg")
        if svg.exists():
            try:
                from PySide6.QtSvg import QSvgRenderer

                renderer = QSvgRenderer(str(svg))
                if renderer.isValid():
                    self._renderer = renderer
            except ImportError:
                self._renderer = None

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._renderer is not None:
            self._renderer.render(painter, QRectF(self.rect()))
        else:
            _paint_mark(painter, QRectF(self.rect()))
        painter.end()
