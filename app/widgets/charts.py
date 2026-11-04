"""Custom-painted charts. No extra packages. Colours match the QSS theme."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

CYAN = QColor("#22D3EE")
TEAL = QColor("#2DD4BF")
GREEN = QColor("#34D399")
AMBER = QColor("#FBBF24")
ROSE = QColor("#FB7185")
MUTED = QColor("#94A3B8")
GRID = QColor("#29364B")
TEXT = QColor("#F1F5F9")
NAVY = QColor("#151F32")


class _ChartBase(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(168)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), NAVY)
        self.draw_chart(painter)
        painter.end()

    def draw_chart(self, painter: QPainter) -> None:
        raise NotImplementedError


class ActivityChart(_ChartBase):
    def __init__(self, points: list[tuple[str, int]], parent=None) -> None:
        super().__init__(parent)
        self.points = points

    def draw_chart(self, painter: QPainter) -> None:
        if not self.points:
            return
        left, top, right, bottom = 48, 10, self.width() - 12, self.height() - 34
        width = max(1, right - left)
        height = max(1, bottom - top)
        max_value = max(value for _label, value in self.points) or 1

        painter.setPen(QPen(GRID, 1))
        for step in range(4):
            y = top + height * step / 3
            painter.drawLine(left, int(y), right, int(y))
            label = int(max_value * (1 - step / 3))
            painter.setPen(MUTED)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(2, y - 8, 42, 16), Qt.AlignmentFlag.AlignRight, str(label))
            painter.setPen(QPen(GRID, 1))

        painter.setPen(MUTED)
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(QRectF(2, 0, 42, 12), Qt.AlignmentFlag.AlignLeft, "Ballots")

        bar_width = width / (len(self.points) * 1.7)
        for index, (label, value) in enumerate(self.points):
            x = left + (index + 0.32) * (width / len(self.points))
            bar_h = (value / max_value) * (height - 6)
            rect = QRectF(x, bottom - bar_h, bar_width, bar_h)
            path = QPainterPath()
            path.addRoundedRect(rect, 4, 4)
            painter.fillPath(path, CYAN)
            painter.setPen(MUTED)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(x - 10, bottom + 3, bar_width + 20, 16),
                Qt.AlignmentFlag.AlignHCenter,
                label,
            )

        painter.setPen(MUTED)
        painter.setFont(QFont("Segoe UI", 7))
        painter.drawText(
            QRectF(left, self.height() - 14, width, 12),
            Qt.AlignmentFlag.AlignHCenter,
            "Hour (demonstration data)",
        )


class ClassificationChart(_ChartBase):
    def __init__(self, valid: int, rejected: int, review: int, parent=None) -> None:
        super().__init__(parent)
        self.slices = [
            ("Valid", valid, GREEN),
            ("Rejected", rejected, ROSE),
            ("Needs review", review, AMBER),
        ]

    def draw_chart(self, painter: QPainter) -> None:
        total = sum(item[1] for item in self.slices) or 1
        size = min(self.width() * 0.48, self.height() - 16)
        rect = QRectF(12, (self.height() - size) / 2, size, size)
        start = 90 * 16
        for _name, value, color in self.slices:
            span = int(value / total * 360 * 16)
            painter.setBrush(color)
            painter.setPen(QPen(NAVY, 3))
            painter.drawPie(rect, start, -span)
            start -= span

        hole = QRectF(rect.center().x() - size * 0.22, rect.center().y() - size * 0.22, size * 0.44, size * 0.44)
        painter.setBrush(NAVY)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(hole)
        painter.setPen(TEXT)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(hole, Qt.AlignmentFlag.AlignCenter, "Demo\nmix")

        legend_x = rect.right() + 14
        y = rect.center().y() - 32
        for name, value, color in self.slices:
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(legend_x, y, 10, 10), 2, 2)
            painter.setPen(TEXT)
            painter.setFont(QFont("Segoe UI", 9))
            percent = value / total * 100
            painter.drawText(
                QRectF(legend_x + 16, y - 4, self.width() - legend_x - 20, 20),
                Qt.AlignmentFlag.AlignLeft,
                f"{name}  {percent:.1f}%",
            )
            y += 24


class CandidateBarChart(_ChartBase):
    def __init__(self, candidates: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.candidates = candidates
        self.setMinimumHeight(120)

    def draw_chart(self, painter: QPainter) -> None:
        if not self.candidates:
            return
        values = [int(item.get("vote_count", item.get("votes", 0))) for item in self.candidates]
        max_votes = max(values) or 1
        top = 8
        left = 148
        right = self.width() - 56
        row_h = (self.height() - 16) / len(self.candidates)
        ordered = sorted(
            self.candidates,
            key=lambda item: -int(item.get("vote_count", item.get("votes", 0))),
        )
        for index, item in enumerate(ordered):
            y = top + index * row_h
            votes = int(item.get("vote_count", item.get("votes", 0)))
            painter.setPen(TEXT)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(6, y, left - 14, row_h - 8),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                item.get("candidate_name", item.get("name", "")),
            )
            bar_w = (votes / max_votes) * max(1, right - left)
            rect = QRectF(left, y + 6, bar_w, max(10, row_h - 16))
            path = QPainterPath()
            path.addRoundedRect(rect, 6, 6)
            painter.fillPath(path, TEAL)
            painter.setPen(MUTED)
            painter.drawText(
                QRectF(rect.right() + 8, y, 52, row_h - 8),
                Qt.AlignmentFlag.AlignVCenter,
                f"{votes:,}",
            )


def activity_chart(points: list[tuple[str, int]]) -> QWidget:
    return ActivityChart(points)


def classification_chart(valid: int, rejected: int, review: int) -> QWidget:
    return ClassificationChart(valid, rejected, review)


def candidate_bar_chart(candidates: list[dict]) -> QWidget:
    return CandidateBarChart(candidates)
