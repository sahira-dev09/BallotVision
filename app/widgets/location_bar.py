"""Shared Negeri/DUN selector used across officer pages."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel

from app.core.constituencies import (
    constituencies_for,
    dun_applicable,
    find_state,
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
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(4)

        negeri_label = QLabel("Negeri")
        negeri_label.setObjectName("fieldCaption")
        self.negeri = SearchableCombo()
        self.negeri.addItems(state_names())
        self.negeri.activated.connect(self._on_negeri)

        dun_label = QLabel("DUN")
        dun_label.setObjectName("fieldCaption")
        self.dun_count = QLabel()
        self.dun_count.setObjectName("hintLabel")
        dun_header = QHBoxLayout()
        dun_header.addWidget(dun_label)
        dun_header.addWidget(self.dun_count, 1)
        self.dun = SearchableCombo()
        self.dun.activated.connect(self._on_dun)

        election_caption = QLabel("Election")
        election_caption.setObjectName("fieldCaption")
        self.election_value = QLabel()
        self.election_value.setObjectName("locationValue")
        batch_caption = QLabel("Batch")
        batch_caption.setObjectName("fieldCaption")
        self.batch_value = QLabel()
        self.batch_value.setObjectName("locationValue")

        status_row = QHBoxLayout()
        self.kind_badge = StatusBadge("No data", "neutral")
        self.location_note = QLabel()
        self.location_note.setObjectName("hintLabel")
        self.location_note.setWordWrap(True)
        status_row.addWidget(self.kind_badge, 0)
        status_row.addWidget(self.location_note, 1)

        layout.addWidget(negeri_label, 0, 0)
        layout.addWidget(self.negeri, 1, 0)
        layout.addLayout(dun_header, 0, 1)
        layout.addWidget(self.dun, 1, 1)
        layout.addWidget(election_caption, 0, 2)
        layout.addWidget(self.election_value, 1, 2)
        layout.addWidget(batch_caption, 0, 3)
        layout.addWidget(self.batch_value, 1, 3)
        layout.addLayout(status_row, 2, 0, 1, 4)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 2)

    def _fill_dun(self, negeri: str, selected_code: str = "") -> None:
        self.dun.clear()
        if not dun_applicable(negeri):
            self.dun.setEnabled(False)
            self.dun.setEditText("DUN not applicable")
            self.dun_count.setText("")
            return
        self.dun.setEnabled(True)
        seats = constituencies_for(negeri)
        self.dun_count.setText(f"{len(seats)} seats")
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
            "prototype_demo": ("warning", "Demo data"),
            "imported_session": ("info", "Imported session"),
            "not_applicable": ("neutral", "No DUN"),
            "none": ("neutral", "No session"),
        }
        badge_kind, badge_text = kind_meta.get(kind, ("neutral", kind))
        self.kind_badge.set_kind(badge_kind, badge_text)
        if not dun_applicable(negeri):
            self.location_note.setText(
                f"{negeri} has parliamentary seats only. DUN selection is not used. {source_label()}"
            )
            return
        self.location_note.setText(
            f"{election.get('dun') or 'Select a DUN'}. Unofficial demonstration figures only. {source_label()}"
        )
