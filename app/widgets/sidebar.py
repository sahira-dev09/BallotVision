"""Left navigation with painted icons and compact system status."""

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import APP_BRAND_TAG, APP_NAME, PAGES
from app.widgets.logo import LogoMark


class NavIcon(QWidget):
    KINDS = {
        "dashboard": "grid",
        "scan": "scan",
        "review": "flag",
        "results": "bars",
        "audit": "list",
        "settings": "gear",
    }

    def __init__(self, page_id: str, parent=None) -> None:
        super().__init__(parent)
        self.page_id = page_id
        self.setFixedSize(18, 18)
        self._active = False

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#22D3EE") if self._active else QColor("#94A3B8")
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        kind = self.KINDS.get(self.page_id, "grid")
        if kind == "grid":
            painter.drawRoundedRect(1, 1, 6, 6, 1, 1)
            painter.drawRoundedRect(11, 1, 6, 6, 1, 1)
            painter.drawRoundedRect(1, 11, 6, 6, 1, 1)
            painter.drawRoundedRect(11, 11, 6, 6, 1, 1)
        elif kind == "scan":
            painter.drawRoundedRect(2, 3, 14, 12, 2, 2)
            painter.drawLine(2, 9, 16, 9)
        elif kind == "flag":
            painter.drawLine(4, 2, 4, 16)
            painter.drawLine(4, 3, 14, 7)
            painter.drawLine(14, 7, 4, 11)
        elif kind == "bars":
            painter.drawLine(3, 15, 3, 9)
            painter.drawLine(8, 15, 8, 4)
            painter.drawLine(13, 15, 13, 7)
        elif kind == "list":
            painter.drawLine(3, 4, 15, 4)
            painter.drawLine(3, 9, 15, 9)
            painter.drawLine(3, 14, 15, 14)
        else:
            painter.drawEllipse(QRect(3, 3, 12, 12))
            painter.drawEllipse(QRect(7, 7, 4, 4))
            for point in ((9, 1), (15, 9), (9, 17), (1, 9)):
                painter.drawPoint(QPoint(*point))


class NavButton(QPushButton):
    def __init__(self, page_id: str, text: str, parent=None) -> None:
        super().__init__(parent)
        self.page_id = page_id
        self.setCheckable(True)
        self.setObjectName("navButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(10)
        self.icon_widget = NavIcon(page_id)
        label = QLabel(text)
        label.setObjectName("navButtonLabel")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.icon_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.count_label = QLabel("")
        self.count_label.setObjectName("navCount")
        self.count_label.setVisible(False)
        self.count_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.icon_widget)
        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(self.count_label)

    def set_count(self, count: int) -> None:
        self.count_label.setVisible(count > 0)
        self.count_label.setText(str(count) if count else "")

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self.icon_widget.set_active(checked)


class Sidebar(QFrame):
    page_chosen = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(236)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 14)
        layout.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        brand.addWidget(LogoMark(36))
        titles = QVBoxLayout()
        titles.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setObjectName("brandTitle")
        tag = QLabel(APP_BRAND_TAG)
        tag.setObjectName("brandTag")
        titles.addWidget(name)
        titles.addWidget(tag)
        brand.addLayout(titles)
        layout.addLayout(brand)
        layout.addSpacing(14)

        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, NavButton] = {}
        for page in PAGES:
            button = NavButton(page["id"], page["nav"])
            self.group.addButton(button)
            self.buttons[page["id"]] = button
            button.clicked.connect(lambda _checked, page_id=page["id"]: self.page_chosen.emit(page_id))
            layout.addWidget(button)

        layout.addStretch()

        status = QFrame()
        status.setObjectName("sidebarStatus")
        status_layout = QVBoxLayout(status)
        status_layout.setContentsMargins(10, 10, 10, 10)
        status_layout.setSpacing(4)
        row = QHBoxLayout()
        dot = QLabel("●")
        dot.setObjectName("statusDot")
        status_text = QLabel("Demo Mode · Ready")
        status_text.setObjectName("mutedLabel")
        row.addWidget(dot)
        row.addWidget(status_text)
        row.addStretch()
        status_layout.addLayout(row)
        engine = QLabel("Recognition is simulated in this prototype.")
        engine.setObjectName("hintLabel")
        engine.setWordWrap(True)
        status_layout.addWidget(engine)
        layout.addWidget(status)

    def set_active(self, page_id: str) -> None:
        button = self.buttons[page_id]
        button.setChecked(True)

    def set_review_count(self, count: int) -> None:
        self.buttons["review"].set_count(count)
