"""Custom-painted charts. No extra packages. Colours match the QSS theme."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

CYAN = QColor("#22D3EE")
GREEN = QColor("#34D399")
AMBER = QColor("#FBBF24")
ROSE = QColor("#FB7185")
MUTED = QColor("#94A3B8")
GRID = QColor("#29364B")
TEXT = QColor("#F1F5F9")
NAVY = QColor("#151F32")

CANDIDATE_PALETTE = (
    "#22D3EE",
    "#A78BFA",
    "#34D399",
    "#FBBF24",
    "#60A5FA",
    "#FB7185",
    "#2DD4BF",
    "#F472B6",
)


def color_for_candidate(record: dict) -> QColor:
    """Stable colour for one candidate across every chart on the page."""
    accent = record.get("accent")
    if isinstance(accent, str) and accent.startswith("#") and QColor(accent).isValid():
        return QColor(accent)
    position = record.get("ballot_position")
    if isinstance(position, int) and position > 0:
        return QColor(CANDIDATE_PALETTE[(position - 1) % len(CANDIDATE_PALETTE)])
    key = str(record.get("candidate_id") or record.get("candidate_name") or "")
    index = sum(ord(char) for char in key) % len(CANDIDATE_PALETTE)
    return QColor(CANDIDATE_PALETTE[index])


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
        self._hits: list[tuple[QRectF, str]] = []
        self.setMinimumHeight(210)
        self.setMouseTracking(True)

    def draw_chart(self, painter: QPainter) -> None:
        self._hits = []
        if not self.points:
            return
        left, top, right, bottom = 52, 16, self.width() - 16, self.height() - 36
        width = max(1, right - left)
        height = max(1, bottom - top)
        max_value = max(value for _label, value in self.points) or 1
        padded_max = max_value * 1.08

        painter.setPen(QPen(GRID, 1))
        for step in range(4):
            y = top + height * step / 3
            painter.drawLine(left, int(y), right, int(y))
            label = int(round(padded_max * (1 - step / 3)))
            painter.setPen(MUTED)
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(0, y - 8, left - 8, 16), Qt.AlignmentFlag.AlignRight, str(label))
            painter.setPen(QPen(GRID, 1))

        painter.setPen(MUTED)
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(QRectF(0, 0, left - 4, 14), Qt.AlignmentFlag.AlignRight, "Ballots")

        coords: list[tuple[float, float, str, int]] = []
        slot = width / len(self.points)
        for index, (label, value) in enumerate(self.points):
            x = left + (index + 0.5) * slot
            y = bottom - (value / padded_max) * height
            coords.append((x, y, label, value))

        area = QPainterPath()
        area.moveTo(coords[0][0], bottom)
        for x, y, _label, _value in coords:
            area.lineTo(x, y)
        area.lineTo(coords[-1][0], bottom)
        area.closeSubpath()
        painter.fillPath(area, QColor(34, 211, 238, 32))

        painter.setPen(QPen(CYAN, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for start, end in zip(coords, coords[1:]):
            painter.drawLine(QPointF(start[0], start[1]), QPointF(end[0], end[1]))

        painter.setFont(QFont("Segoe UI", 8))
        for x, y, label, value in coords:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(NAVY)
            painter.drawEllipse(QPointF(x, y), 5.5, 5.5)
            painter.setBrush(CYAN)
            painter.drawEllipse(QPointF(x, y), 3.5, 3.5)
            painter.setPen(MUTED)
            painter.drawText(
                QRectF(x - slot / 2, bottom + 6, slot, 16),
                Qt.AlignmentFlag.AlignHCenter,
                label,
            )
            self._hits.append((QRectF(x - 14, y - 14, 28, 28), f"{label}  ·  {value:,} ballots"))

        painter.setPen(MUTED)
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRectF(left, self.height() - 14, width, 12),
            Qt.AlignmentFlag.AlignHCenter,
            "Hour",
        )

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        point = event.position()
        for rect, text in self._hits:
            if rect.contains(point):
                QToolTip.showText(event.globalPosition().toPoint(), text, self)
                return
        QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        QToolTip.hideText()
        super().leaveEvent(event)


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
        self.setMinimumHeight(max(180, 48 * max(1, len(candidates))))

    def draw_chart(self, painter: QPainter) -> None:
        if not self.candidates:
            return
        values = [int(item.get("vote_count", item.get("votes", 0))) for item in self.candidates]
        max_votes = max(values) or 1
        top = 10
        left = 148
        right = self.width() - 64
        row_h = (self.height() - 20) / len(self.candidates)
        ordered = sorted(
            self.candidates,
            key=lambda item: -int(item.get("vote_count", item.get("votes", 0))),
        )
        for index, item in enumerate(ordered):
            y = top + index * row_h
            votes = int(item.get("vote_count", item.get("votes", 0)))
            color = color_for_candidate(item)
            painter.setPen(TEXT)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                QRectF(8, y, left - 18, row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                item.get("candidate_name", item.get("name", "")),
            )
            bar_h = max(12, min(16, row_h - 22))
            bar_w = (votes / max_votes) * max(1, right - left)
            rect = QRectF(left, y + (row_h - bar_h) / 2, bar_w, bar_h)
            path = QPainterPath()
            path.addRoundedRect(rect, 7, 7)
            painter.fillPath(path, color)
            painter.setPen(MUTED)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(
                QRectF(rect.right() + 8, y, 56, row_h),
                Qt.AlignmentFlag.AlignVCenter,
                f"{votes:,}",
            )


def activity_chart(points: list[tuple[str, int]]) -> QWidget:
    return ActivityChart(points)


def classification_chart(valid: int, rejected: int, review: int) -> QWidget:
    return ClassificationChart(valid, rejected, review)


def candidate_bar_chart(candidates: list[dict]) -> QWidget:
    return CandidateBarChart(candidates)
