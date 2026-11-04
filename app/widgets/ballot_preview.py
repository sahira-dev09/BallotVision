"""Painted simulated ballot. This is not a real SPR ballot scan."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from app.core.constants import CANDIDATES


class SimulatedBallotView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 240)
        self.ballot_id = "—"
        self.detected = ""
        self.reason = "No ballot selected"
        self.confidence = None
        self.status = "Pending Review"

    def set_ballot(self, ballot: dict | None) -> None:
        if not ballot:
            self.ballot_id = "—"
            self.detected = ""
            self.reason = "No ballot selected"
            self.confidence = None
            self.status = ""
        else:
            self.ballot_id = ballot["id"]
            self.detected = ballot.get("detected", "")
            self.reason = ballot.get("reason", "")
            raw = ballot.get("confidence")
            self.confidence = int(raw) if raw is not None else None
            self.status = ballot.get("status", "")
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor("#0B1120"))

        margin = 18
        paper = QRectF(margin, margin, self.width() - margin * 2, self.height() - margin * 2)
        path = QPainterPath()
        path.addRoundedRect(paper, 10, 10)
        painter.fillPath(path, QColor("#F8FAFC"))
        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.drawPath(path)

        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(
            QRectF(paper.x() + 18, paper.y() + 16, paper.width() - 36, 24),
            Qt.AlignmentFlag.AlignLeft,
            "SIMULATED BALLOT  ·  DEMO ONLY",
        )
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#475569"))
        painter.drawText(
            QRectF(paper.x() + 18, paper.y() + 40, paper.width() - 36, 18),
            Qt.AlignmentFlag.AlignLeft,
            f"{self.ballot_id}    Not a live SPR scan",
        )

        header = QRectF(paper.x() + 18, paper.y() + 68, paper.width() - 36, 28)
        painter.fillRect(header, QColor("#E2E8F0"))
        painter.setPen(QColor("#0F172A"))
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        painter.drawText(header.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter, "Mark one candidate only")

        footer_h = 52
        row_top = header.bottom() + 10
        available = paper.bottom() - footer_h - 12 - row_top
        row_height = max(32, min(48, available / len(CANDIDATES) - 8))
        for index, name in enumerate(CANDIDATES):
            y = row_top + index * (row_height + 8)
            row = QRectF(paper.x() + 18, y, paper.width() - 36, row_height)
            painter.setPen(QPen(QColor("#94A3B8"), 1))
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(row, 6, 6)

            box_size = min(22, row_height - 10)
            box = QRectF(row.x() + 14, row.y() + (row_height - box_size) / 2, box_size, box_size)
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(QPen(QColor("#0F172A"), 1.6))
            painter.drawRect(box)

            marked = bool(self.detected) and name == self.detected
            if marked:
                painter.setPen(QPen(QColor("#0F172A"), 2.4))
                painter.drawLine(
                    int(box.left() + 4),
                    int(box.top() + 4),
                    int(box.right() - 4),
                    int(box.bottom() - 4),
                )
                painter.drawLine(
                    int(box.right() - 4),
                    int(box.top() + 4),
                    int(box.left() + 4),
                    int(box.bottom() - 4),
                )

            painter.setPen(QColor("#0F172A"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                QRectF(box.right() + 14, row.y(), row.width() - 60, row.height()),
                Qt.AlignmentFlag.AlignVCenter,
                name,
            )

        footer = QRectF(paper.x() + 18, paper.bottom() - footer_h - 10, paper.width() - 36, footer_h)
        painter.fillRect(footer, QColor("#FEF3C7"))
        painter.setPen(QColor("#92400E"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(
            footer.adjusted(10, 8, -10, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
            f"Simulated mark detection\nFlag: {self.reason}\n"
            f"{'No confidence score — engine not connected' if self.confidence is None else f'Confidence {self.confidence}%'}  ·  {self.status}",
        )
