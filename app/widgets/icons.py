"""Small painted icons used in cards, headers, and menus."""

from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class PaintedIcon(QWidget):
    def __init__(self, kind: str, color: str = "#22D3EE", size: int = 18, parent=None) -> None:
        super().__init__(parent)
        self.kind = kind
        self.color = QColor(color)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self.color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        kind = self.kind
        w, h = self.width(), self.height()
        if kind == "layers":
            painter.drawRoundedRect(3, 7, w - 6, h - 11, 2, 2)
            painter.drawLine(5, 5, w - 5, 5)
            painter.drawLine(7, 3, w - 7, 3)
        elif kind == "shield":
            path = QPainterPath()
            path.moveTo(w / 2, 2)
            path.lineTo(w - 3, 6)
            path.lineTo(w - 3, 11)
            path.quadTo(w / 2, h - 1, 3, 11)
            path.lineTo(3, 6)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(int(w * 0.32), int(h * 0.52), int(w * 0.46), int(h * 0.68))
            painter.drawLine(int(w * 0.46), int(h * 0.68), int(w * 0.70), int(h * 0.36))
        elif kind == "alert":
            path = QPainterPath()
            path.moveTo(w / 2, 2)
            path.lineTo(w - 2, h - 3)
            path.lineTo(2, h - 3)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(w / 2, 7, w / 2, h - 8)
            painter.drawPoint(QPoint(int(w / 2), h - 5))
        elif kind == "info":
            painter.drawEllipse(QRect(1, 1, w - 3, h - 3))
            painter.drawLine(w / 2, 8, w / 2, h - 5)
            painter.drawPoint(QPoint(int(w / 2), 5))
        elif kind == "chevron":
            painter.drawLine(5, 7, w / 2, h - 6)
            painter.drawLine(w / 2, h - 6, w - 5, 7)
        elif kind == "user":
            painter.drawEllipse(QRectF(w * 0.30, 2, w * 0.40, h * 0.40))
            path = QPainterPath()
            path.moveTo(3, h - 3)
            path.quadTo(w / 2, h * 0.48, w - 3, h - 3)
            painter.drawPath(path)
        elif kind == "mail":
            painter.drawRoundedRect(2, 4, w - 4, h - 8, 2, 2)
            painter.drawLine(3, 5, w / 2, h * 0.55)
            painter.drawLine(w / 2, h * 0.55, w - 3, 5)
        elif kind == "about":
            painter.drawRoundedRect(4, 2, w - 8, h - 4, 2, 2)
            painter.drawLine(7, 6, w - 7, 6)
            painter.drawLine(7, 10, w - 7, 10)
            painter.drawLine(7, 14, w - 9, 14)
        elif kind == "demo":
            painter.drawEllipse(QRect(2, 2, w - 5, h - 5))
            painter.drawLine(w * 0.62, h * 0.62, w - 2, h - 2)
        elif kind == "gear":
            painter.drawEllipse(QRect(5, 5, w - 11, h - 11))
            painter.drawEllipse(QRect(7, 7, w - 15, h - 15))
            for point in ((w / 2, 1), (w - 2, h / 2), (w / 2, h - 2), (1, h / 2)):
                painter.drawPoint(QPoint(int(point[0]), int(point[1])))
        elif kind == "clock":
            painter.drawEllipse(QRect(1, 1, w - 3, h - 3))
            painter.drawLine(w / 2, w / 2, w / 2, 5)
            painter.drawLine(w / 2, w / 2, w - 5, w / 2)
        else:
            painter.drawRoundedRect(2, 2, w - 4, h - 4, 2, 2)
        painter.end()
