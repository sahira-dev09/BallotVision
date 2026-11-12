"""Officer review of queued ballots — decide, submit, next ballot."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.widgets.ballot_preview import SimulatedBallotView
from app.widgets.components import (
    Card,
    EmptyState,
    NoticeBar,
    SectionTitle,
    StatusBadge,
    aligned_item,
    style_data_table,
)
from app.widgets.location_bar import LocationBar

DECISIONS = (
    ("Confirm Detected Mark", "Confirm mark"),
    ("Mark as Rejected", "Reject ballot"),
    ("Send for Further Review", "Send for further review"),
)

_CONFIDENCE_BADGE = {
    "High confidence": ("success", "High Confidence"),
    "Low confidence": ("warning", "Low Confidence"),
    "Not detected": ("neutral", "Not Detected"),
}


def _confidence_kind(status: str) -> tuple[str, str]:
    return _CONFIDENCE_BADGE.get(status, ("neutral", "Not Detected"))


class DecisionDialog(QDialog):
    """Confirmation shell. Accept still means the officer confirmed the decision."""

    def __init__(self, ballot_id: str, decision_label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("confirmDialog")
        self.setWindowTitle("Submit decision")
        self.setModal(True)
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)
        title = QLabel("Submit this decision?")
        title.setObjectName("sectionTitle")
        body = QLabel(
            f"{ballot_id}\n{decision_label}\n\n"
            "This stores the decision in the current session, with the ballot, image reference, "
            "review reason, officer, and time. It is not written to an election database."
        )
        body.setObjectName("mutedLabel")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton("Submit decision")
        confirm.setObjectName("primaryButton")
        confirm.setDefault(True)
        confirm.clicked.connect(self.accept)
        actions.addWidget(cancel)
        actions.addWidget(confirm)
        layout.addLayout(actions)


class ReviewPage(QScrollArea):
    navigate = Signal(str)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.selected_id = None
        self.filter_name = "Pending Review"
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName("pageScroll")

        body = QWidget()
        body.setObjectName("pageBody")
        self.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 12, 24, 16)
        root.setSpacing(10)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        root.addWidget(
            NoticeBar(
                "This queue is for ballots that were not counted automatically. "
                "A submitted decision is kept for this session only.",
                "info",
            )
        )
        self.location = LocationBar()
        self.location.location_changed.connect(self.store.set_demo_location)
        root.addWidget(self.location)

        self.workspace = QWidget()
        columns = QHBoxLayout(self.workspace)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(12)
        columns.addWidget(self._build_queue(), 5)
        columns.addWidget(self._build_detail(), 7)
        root.addWidget(self.workspace, 1)

        self.empty_cta = EmptyState(
            "Review queue is clear",
            "There are no flagged ballots waiting in this constituency. Inspect unofficial results, or import another image.",
            "Open vote results",
        )
        self.empty_cta.action.clicked.connect(lambda: self.navigate.emit("results"))
        self.empty_cta.setVisible(False)
        root.addWidget(self.empty_cta)

        self.store.changed.connect(self.refresh)
        self.refresh()

    def on_page_shown(self) -> None:
        default = self.store.settings().get("default_review_filter", "Pending Review")
        if default in self.filter_buttons:
            self.filter_buttons[default].click()

    def _build_queue(self) -> Card:
        card = Card()
        self.queue_heading = QLabel("Flagged ballots")
        self.queue_heading.setObjectName("sectionTitle")
        self.queue_sub = QLabel("Select a ballot, then decide on the right.")
        self.queue_sub.setObjectName("mutedLabel")
        self.queue_sub.setWordWrap(True)
        card.layout.addWidget(self.queue_heading)
        card.layout.addWidget(self.queue_sub)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search ballot ID or reason")
        self.search.textChanged.connect(self.refresh)
        card.layout.addWidget(self.search)

        filters = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        self.filter_buttons = {}
        for name in ("Pending Review", "Reviewed", "All"):
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, value=name: self._set_filter(value))
            self.filter_group.addButton(button)
            self.filter_buttons[name] = button
            filters.addWidget(button)
        filters.addStretch()
        self.filter_buttons["Pending Review"].setChecked(True)
        card.layout.addLayout(filters)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Ballot ID", "Review reason", "Review status"])
        style_data_table(self.table)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_select)
        card.layout.addWidget(self.table, 1)
        self.empty = QLabel("No ballots match this filter.")
        self.empty.setObjectName("mutedLabel")
        card.layout.addWidget(self.empty)
        return card

    def _build_detail(self) -> Card:
        card = Card()
        card.layout.addWidget(
            SectionTitle("Inspect and decide", "Confirm, reject, or send on. Submit records the decision.")
        )
        self.imported_preview = QLabel("No ballot selected")
        self.imported_preview.setObjectName("previewFrame")
        self.imported_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imported_preview.setWordWrap(True)
        self.imported_preview.setMinimumHeight(220)
        self.imported_preview.setVisible(False)
        card.layout.addWidget(self.imported_preview, 1)
        self.preview = SimulatedBallotView()
        card.layout.addWidget(self.preview, 1)

        self.meta_id = QLabel("No ballot selected")
        self.meta_id.setObjectName("reviewBallotId")
        card.layout.addWidget(QLabel("Ballot ID"))
        card.layout.addWidget(self.meta_id)

        negeri_caption = QLabel("Negeri")
        negeri_caption.setObjectName("fieldCaption")
        self.review_negeri = QLabel("Not recorded")
        self.review_negeri.setObjectName("reviewNegeri")
        self.review_negeri.setWordWrap(True)
        dun_caption = QLabel("DUN")
        dun_caption.setObjectName("fieldCaption")
        self.review_dun = QLabel("Not recorded")
        self.review_dun.setObjectName("reviewDun")
        self.review_dun.setWordWrap(True)
        card.layout.addWidget(negeri_caption)
        card.layout.addWidget(self.review_negeri)
        card.layout.addWidget(dun_caption)
        card.layout.addWidget(self.review_dun)

        confidence_caption = QLabel("OCR confidence")
        confidence_caption.setObjectName("fieldCaption")
        self.confidence = StatusBadge("Not recorded", "neutral")
        self.confidence.setObjectName("reviewConfidence")
        mark_caption = QLabel("Candidate mark confidence")
        mark_caption.setObjectName("fieldCaption")
        self.mark_confidence = StatusBadge("Not recorded", "neutral")
        self.mark_confidence.setObjectName("reviewMarkConfidence")
        status_caption = QLabel("Review status")
        status_caption.setObjectName("fieldCaption")
        self.status_badge = StatusBadge("No selection", "neutral")
        self.status_badge.setObjectName("reviewStatus")
        card.layout.addWidget(confidence_caption)
        card.layout.addWidget(self.confidence, 0, Qt.AlignmentFlag.AlignLeft)
        card.layout.addWidget(mark_caption)
        card.layout.addWidget(self.mark_confidence, 0, Qt.AlignmentFlag.AlignLeft)
        card.layout.addWidget(status_caption)
        card.layout.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignLeft)

        reason_caption = QLabel("Review reason")
        reason_caption.setObjectName("fieldCaption")
        self.meta_reason = QLabel("")
        self.meta_reason.setWordWrap(True)
        self.meta_reason.setObjectName("reviewReason")
        card.layout.addWidget(reason_caption)
        card.layout.addWidget(self.meta_reason)
        self.candidate_check = QLabel("")
        self.candidate_check.setObjectName("candidateCheck")
        self.candidate_check.setWordWrap(True)
        card.layout.addWidget(self.candidate_check)

        decision_caption = QLabel("Decision")
        decision_caption.setObjectName("fieldCaption")
        card.layout.addWidget(decision_caption)
        self.decision_group = QButtonGroup(self)
        self.decision_group.setExclusive(True)
        decisions = QHBoxLayout()
        decisions.setSpacing(8)
        self.decision_buttons = {}
        for value, label in DECISIONS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("choice", False)
            button.clicked.connect(self._sync_decision_styles)
            self.decision_group.addButton(button)
            self.decision_buttons[value] = button
            decisions.addWidget(button)
        card.layout.addLayout(decisions)

        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Optional notes")
        self.notes.setFixedHeight(48)
        card.layout.addWidget(self.notes)

        actions = QHBoxLayout()
        submit = QPushButton("Submit decision")
        submit.setObjectName("primaryButton")
        submit.clicked.connect(self._submit)
        self.next_hint = QLabel("After submit, the next pending ballot opens.")
        self.next_hint.setObjectName("hintLabel")
        actions.addWidget(submit)
        actions.addWidget(self.next_hint, 1)
        card.layout.addLayout(actions)
        return card

    def _set_filter(self, name: str) -> None:
        self.filter_name = name
        self.refresh()

    def _filtered(self) -> list[dict]:
        query = self.search.text().strip().lower()
        rows = []
        for ballot in self.store.data["flagged"]:
            if self.filter_name != "All" and ballot["status"] != self.filter_name:
                continue
            blob = f"{ballot['id']} {ballot['reason']}".lower()
            if query and query not in blob:
                continue
            rows.append(ballot)
        return rows

    def refresh(self) -> None:
        election = self.store.data.get("election", {})
        self.location.apply_election(election)
        flagged = self.store.data["flagged"]
        pending = sum(1 for item in flagged if item["status"] == "Pending Review")
        self.queue_heading.setText(f"Flagged ballots · {pending} pending")
        self.queue_sub.setText(f"{election.get('dun') or 'This constituency'} · {len(flagged)} in queue")
        self.empty_cta.setVisible(not flagged)
        self.workspace.setVisible(bool(flagged))
        rows = self._filtered()
        self.table.setRowCount(len(rows))
        self.empty.setVisible(not rows)
        selected_row = 0
        for index, ballot in enumerate(rows):
            values = [ballot["id"], ballot["reason"], ballot["status"]]
            for column, value in enumerate(values):
                self.table.setItem(index, column, aligned_item(value))
            if ballot["id"] == self.selected_id:
                selected_row = index
        self.table.resizeRowsToContents()
        if rows:
            self.table.selectRow(selected_row)
            self._apply_ballot(rows[selected_row])
        else:
            self.selected_id = None
            self._apply_ballot(None)

    def _on_select(self) -> None:
        row = self.table.currentRow()
        rows = self._filtered()
        if 0 <= row < len(rows):
            self.selected_id = rows[row]["id"]
            self._apply_ballot(rows[row])

    def _apply_ballot(self, ballot: dict | None) -> None:
        self._show_ballot_image(ballot)
        if not ballot:
            self.meta_id.setText("No ballot selected")
            self.review_negeri.setText("Not recorded")
            self.review_dun.setText("Not recorded")
            self.meta_reason.setText("Choose a row in the queue.")
            self.candidate_check.setText("")
            self.confidence.set_kind("neutral", "Not recorded")
            self.mark_confidence.set_kind("neutral", "Not recorded")
            self.status_badge.set_kind("neutral", "No selection")
            self.notes.clear()
            return
        self.meta_id.setText(ballot["id"])
        negeri = (ballot.get("suggested_negeri") or "").strip()
        dun = f"{ballot.get('suggested_dun_code') or ''} {ballot.get('suggested_dun_name') or ''}".strip()
        has_reading = bool(ballot.get("ocr_status") or ballot.get("source_path"))
        if has_reading:
            self.review_negeri.setText(negeri or "Location Not Detected")
            self.review_dun.setText(dun or "Location Not Detected")
            self.confidence.set_kind(*_confidence_kind(ballot.get("match_status") or ""))
            self.mark_confidence.set_kind(*_confidence_kind(ballot.get("mark_confidence") or ""))
        else:
            self.review_negeri.setText("Not recorded")
            self.review_dun.setText("Not recorded")
            self.confidence.set_kind("neutral", "Not recorded")
            self.mark_confidence.set_kind("neutral", "Not recorded")
        self.meta_reason.setText(ballot.get("reason") or "")
        if ballot.get("candidate_mismatch"):
            self.candidate_check.setText(ballot.get("mismatch_reason") or "")
        elif ballot.get("detected"):
            self.candidate_check.setText(f"Candidate: {ballot['detected']}")
        elif ballot.get("source_path") or ballot.get("ocr_status"):
            self.candidate_check.setText("Candidate: Not Detected")
        else:
            self.candidate_check.setText("")
        kind = "success" if ballot["status"] == "Reviewed" else "warning"
        self.status_badge.set_kind(kind, ballot["status"])
        self.notes.setPlainText(ballot.get("notes", ""))
        for button in self.decision_buttons.values():
            button.setChecked(False)
        if ballot.get("decision") in self.decision_buttons:
            self.decision_buttons[ballot["decision"]].setChecked(True)
        self._sync_decision_styles()

    def _show_ballot_image(self, ballot: dict | None) -> None:
        path = str((ballot or {}).get("source_path") or "")
        if not path:
            self.imported_preview.setVisible(False)
            self.imported_preview.setPixmap(QPixmap())
            self.imported_preview.setToolTip("")
            self.preview.setVisible(True)
            self.preview.set_ballot(ballot)
            return
        self.preview.setVisible(False)
        self.imported_preview.setVisible(True)
        self.imported_preview.setToolTip(path)
        file_path = Path(path)
        pixmap = QPixmap(str(file_path)) if file_path.is_file() else QPixmap()
        if pixmap.isNull():
            self.imported_preview.setPixmap(QPixmap())
            self.imported_preview.setText("The original ballot image could not be opened.")
            return
        self.imported_preview.setText("")
        scaled = pixmap.scaled(
            QSize(640, 420),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.imported_preview.setPixmap(scaled)

    def _sync_decision_styles(self) -> None:
        for button in self.decision_buttons.values():
            button.setProperty("choice", button.isChecked())
            button.style().unpolish(button)
            button.style().polish(button)

    def _current_decision(self) -> str | None:
        for value, button in self.decision_buttons.items():
            if button.isChecked():
                return value
        return None

    def _next_pending_id(self, exclude: str) -> str | None:
        for ballot in self.store.data["flagged"]:
            if ballot["status"] == "Pending Review" and ballot["id"] != exclude:
                return ballot["id"]
        return None

    def _submit(self) -> None:
        if not self.selected_id:
            QMessageBox.warning(self, "No ballot selected", "Choose a ballot from the queue first.")
            return
        decision = self._current_decision()
        if not decision:
            QMessageBox.warning(self, "Choose a decision", "Confirm mark, reject the ballot, or send it for further review.")
            return
        if self.store.settings().get("require_reviewer_confirmation", True):
            dialog = DecisionDialog(self.selected_id, self.decision_buttons[decision].text(), self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
        submitted = self.selected_id
        self.store.submit_review(submitted, decision, self.notes.toPlainText().strip())
        nxt = self._next_pending_id(submitted)
        if nxt:
            self.filter_name = "Pending Review"
            self.filter_buttons["Pending Review"].setChecked(True)
            self.selected_id = nxt
        else:
            self.selected_id = submitted
        self.refresh()
