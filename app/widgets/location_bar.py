"""Shared Negeri/DUN selector used across officer pages."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from app.core.constituencies import (
    constituencies_for,
    dun_applicable,
    source_label,
    state_names,
)
from app.widgets.components import SearchableCombo, StatusBadge


class LocationBar(QFrame):
    location_changed = Signal(str, str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("locationBar")
        self._updating = False
        layout = QGridLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(8)

        negeri_label = QLabel("Negeri")
        negeri_label.setObjectName("fieldCaption")
        self.negeri = SearchableCombo()
        self.negeri.setMinimumWidth(200)
        self.negeri.addItems(state_names())
        self.negeri.activated.connect(self._on_negeri)

        dun_label = QLabel("DUN")
        dun_label.setObjectName("fieldCaption")
        self.dun_count = QLabel()
        self.dun_count.setObjectName("seatCount")
        self.dun_count.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.dun_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dun_header = QHBoxLayout()
        dun_header.setSpacing(8)
        dun_header.addWidget(dun_label, 0, Qt.AlignmentFlag.AlignVCenter)
        dun_header.addWidget(self.dun_count, 0, Qt.AlignmentFlag.AlignVCenter)
        dun_header.addStretch(1)
        self.dun = SearchableCombo()
        self.dun.setMinimumWidth(240)
        self.dun.activated.connect(self._on_dun)

        self.meta = QFrame()
        self.meta.setObjectName("locationMeta")
        self.meta.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        meta_layout = QHBoxLayout(self.meta)
        meta_layout.setContentsMargins(14, 8, 14, 8)
        meta_layout.setSpacing(18)
        meta_layout.addLayout(self._meta_block("Election", "election_value"))
        meta_layout.addWidget(self._meta_rule())
        meta_layout.addLayout(self._meta_block("Batch", "batch_value"))

        self.kind_badge = StatusBadge("No session", "neutral")
        self.location_note = QLabel()
        self.location_note.setObjectName("hintLabel")
        self.location_note.setWordWrap(True)

        layout.addWidget(negeri_label, 0, 0)
        layout.addWidget(self.negeri, 1, 0)
        layout.addWidget(self.kind_badge, 2, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addLayout(dun_header, 0, 1)
        layout.addWidget(self.dun, 1, 1)
        layout.addWidget(self.meta, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.location_note, 2, 1, 1, 2)
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(1, 4)
        layout.setColumnStretch(2, 0)

    def _meta_block(self, caption: str, attr: str) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(2)
        label = QLabel(caption)
        label.setObjectName("fieldCaption")
        value = QLabel("—")
        value.setObjectName("locationValue")
        value.setWordWrap(True)
        value.setMaximumWidth(210 if attr == "election_value" else 110)
        setattr(self, attr, value)
        column.addWidget(label)
        column.addWidget(value)
        return column

    def _meta_rule(self) -> QFrame:
        rule = QFrame()
        rule.setObjectName("metaRule")
        rule.setFixedWidth(1)
        rule.setMinimumHeight(28)
        return rule

    def _fill_dun(self, negeri: str, selected_code: str = "") -> None:
        self.dun.clear()
        if not dun_applicable(negeri):
            self.dun.setEnabled(False)
            self.dun.setEditText("DUN not applicable")
            self.dun_count.setText("")
            self.dun_count.setVisible(False)
            return
        self.dun.setEnabled(True)
        seats = constituencies_for(negeri)
        self.dun_count.setText(f"{len(seats)} seats")
        self.dun_count.setVisible(bool(seats))
        selected_index = 0
        for index, seat in enumerate(seats):
            self.dun.addItem(seat["label"], seat["code"])
            if seat["code"] == selected_code:
                selected_index = index
        if seats:
            self.dun.setCurrentIndex(selected_index)

    def _on_negeri(self, index: int) -> None:
        if self._updating:
            return
        negeri = self.negeri.itemText(index) if index >= 0 else self.negeri.currentText()
        self._updating = True
        self._fill_dun(negeri)
        self._updating = False
        self._emit()

    def _on_dun(self, index: int) -> None:
        if self._updating or not self.dun.isEnabled():
            return
        self._emit()

    def _emit(self) -> None:
        negeri = self.negeri.currentText()
        code = self.dun.currentData() or ""
        label = self.dun.currentText()
        name = label.replace(str(code), "", 1).strip() if code else ""
        self.location_changed.emit(negeri, code, name)

    def apply_election(self, election: dict) -> None:
        self._updating = True
        self.negeri.setCurrentText(election.get("negeri", ""))
        self._fill_dun(election.get("negeri", ""), election.get("dun_code", ""))
        self._updating = False
        self.election_value.setText(election.get("name", "—"))
        self.batch_value.setText(election.get("batch") or "—")
        negeri = election.get("negeri", "")
        kind = election.get("data_kind", "none")
        kind_meta = {
            "prototype_demo": ("warning", "DEMO DATA"),
            "imported_session": ("info", "Imported session"),
            "not_applicable": ("neutral", "No DUN"),
            "none": ("neutral", "No session"),
        }
        badge_kind, badge_text = kind_meta.get(kind, ("neutral", kind))
        self.kind_badge.set_kind(badge_kind, badge_text)
        if not dun_applicable(negeri):
            self.location_note.setText(
                f"{negeri} has parliamentary seats only, so DUN selection is not used. {source_label()}"
            )
            return
        self.location_note.setText(source_label())
