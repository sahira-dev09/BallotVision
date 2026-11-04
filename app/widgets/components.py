"""Reusable cards, badges, and section headers."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QVBoxLayout,
    QWidget,
)

from app.widgets.icons import PaintedIcon

_CHEVRON_WIDTH = 32


class SearchableCombo(QComboBox):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("locationCombo")
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        completer = self.completer()
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setMaxVisibleItems(12)
        editor = self.lineEdit()
        editor.setReadOnly(False)
        editor.setPlaceholderText("Select")
        editor.setCursor(Qt.CursorShape.PointingHandCursor)
        editor.installEventFilter(self)
        self._fit_editor()

    def _fit_editor(self) -> None:
        editor = self.lineEdit()
        if editor is None:
            return
        height = max(20, self.height() - 4)
        width = max(24, self.width() - _CHEVRON_WIDTH - 12)
        editor.setGeometry(10, 2, width, height)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_editor()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if rect.width() < 8 or rect.height() < 8:
            rect.setRect(self.width() - _CHEVRON_WIDTH, 0, _CHEVRON_WIDTH, self.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#22D3EE") if self.isEnabled() else QColor("#64748B")
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        cx = rect.center().x()
        cy = rect.center().y() + 1
        painter.drawLine(cx - 5, cy - 2, cx, cy + 3)
        painter.drawLine(cx, cy + 3, cx + 5, cy - 2)
        painter.end()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.lineEdit() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton and self.isEnabled() and self.count():
                self.showPopup()
        return super().eventFilter(watched, event)


class Card(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(8)


class StatCard(Card):
    def __init__(
        self,
        label: str,
        value: str,
        hint: str = "",
        icon: str | None = None,
        icon_color: str = "#22D3EE",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        self.icon_wrap = QFrame()
        self.icon_wrap.setObjectName("metricIcon")
        icon_layout = QHBoxLayout(self.icon_wrap)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon:
            icon_layout.addWidget(PaintedIcon(icon, icon_color, 18))
            self.icon_wrap.setProperty("tone", icon)
            self.icon_wrap.style().unpolish(self.icon_wrap)
            self.icon_wrap.style().polish(self.icon_wrap)
        self.icon_wrap.setFixedSize(36, 36)
        header.addWidget(self.icon_wrap, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(2)
        caption = QLabel(label)
        caption.setObjectName("mutedLabel")
        caption.setWordWrap(True)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.value_label.setWordWrap(True)
        text.addWidget(caption)
        text.addWidget(self.value_label)
        header.addLayout(text, 1)
        self.layout.addLayout(header)

        self.hint_label = QLabel(hint)
        self.hint_label.setObjectName("hintLabel")
        self.hint_label.setWordWrap(True)
        self.hint_label.setVisible(bool(hint))
        self.layout.addWidget(self.hint_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_hint(self, hint: str) -> None:
        self.hint_label.setText(hint)
        self.hint_label.setVisible(bool(hint))


class StatusBadge(QLabel):
    def __init__(self, text: str, kind: str = "info", parent=None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_kind(kind, text)

    def set_kind(self, kind: str, text: str | None = None) -> None:
        if text is not None:
            self.setText(text)
        self.setProperty("badge", kind)
        self.style().unpolish(self)
        self.style().polish(self)


class SectionTitle(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("mutedLabel")
            sub.setWordWrap(True)
            layout.addWidget(sub)


class NoticeBar(QFrame):
    def __init__(self, text: str, kind: str = "warning", parent=None) -> None:
        super().__init__(parent)
        self.setProperty("notice", kind)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setObjectName("noticeText")
        layout.addWidget(label)


class EmptyState(QFrame):
    def __init__(self, title: str, body: str, action_label: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("emptyState")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel(body)
        text.setObjectName("mutedLabel")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        layout.addWidget(text)
        self.action = QPushButton(action_label or "Continue")
        self.action.setObjectName("primaryButton")
        self.action.setVisible(bool(action_label))
        layout.addWidget(self.action, 0, Qt.AlignmentFlag.AlignCenter)
