"""Officer overview: constituency, workload, and the next required action."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.utils import format_number, format_percent
from app.widgets.candidate_rows import CandidateList
from app.widgets.charts import activity_chart
from app.widgets.components import Card, EmptyState, SectionTitle, StatCard, StatusBadge
from app.widgets.location_bar import LocationBar


class EventRow(QFrame):
    def __init__(self, event: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("eventRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        time = QLabel(event["time"])
        time.setObjectName("eventTime")
        time.setFixedWidth(48)
        text = QVBoxLayout()
        text.setSpacing(1)
        description = QLabel(event["description"])
        description.setWordWrap(True)
        batch = QLabel(event.get("batch") or "—")
        batch.setObjectName("hintLabel")
        text.addWidget(description)
        text.addWidget(batch)
        status = event.get("status", "Completed")
        kind = {"Completed": "success", "In Progress": "info", "Needs Review": "warning"}.get(status, "neutral")
        layout.addWidget(time, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text, 1)
        layout.addWidget(StatusBadge(status, kind), 0, Qt.AlignmentFlag.AlignTop)


class DashboardPage(QWidget):
    navigate = Signal(str)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setObjectName("pageBody")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 10, 24, 12)
        self.root.setSpacing(8)
        self.location = LocationBar()
        self.location.location_changed.connect(self.store.set_demo_location)
        self.root.addWidget(self.location)
        self.metrics = self._build_metrics()
        self.root.addWidget(self.metrics)
        self.root.addWidget(self._build_action_row())
        self.candidate_card = Card()
        header = QHBoxLayout()
        header.addWidget(
            SectionTitle("Candidate vote overview", "Same unofficial totals as Vote Results"),
            1,
        )
        self.results_link = QPushButton("Open full results")
        self.results_link.setObjectName("ghostButton")
        self.results_link.clicked.connect(lambda: self.navigate.emit("results"))
        header.addWidget(self.results_link, 0, Qt.AlignmentFlag.AlignRight)
        self.candidate_card.layout.addLayout(header)
        self.candidate_list = CandidateList()
        self.candidate_card.layout.addWidget(self.candidate_list)
        self.root.addWidget(self.candidate_card)
        self.overview = self._build_overview()
        self.root.addLayout(self.overview, 1)
        self.empty = EmptyState(
            "No ballots for this constituency",
            "Demonstration figures exist only for Johor N.01 Buloh Kasap. "
            "Other DUN seats stay empty until you import images here.",
            "Import ballot image",
        )
        self.empty.action.clicked.connect(lambda: self.navigate.emit("scan"))
        self.empty.setVisible(False)
        self.root.addWidget(self.empty, 1)
        self.store.changed.connect(self.refresh)
        self.refresh()

    def _build_metrics(self) -> QWidget:
        wrap = QWidget()
        stats_row = QGridLayout(wrap)
        stats_row.setContentsMargins(0, 0, 0, 0)
        stats_row.setHorizontalSpacing(10)
        self.card_total = StatCard("Ballots counted", "0", icon="layers", icon_color="#22D3EE")
        self.card_valid = StatCard("Valid votes", "0", icon="shield", icon_color="#34D399")
        self.card_flagged = StatCard("Need review", "0", icon="alert", icon_color="#FBBF24")
        for column, card in enumerate((self.card_total, self.card_valid, self.card_flagged)):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(card, 0, column)
            stats_row.setColumnStretch(column, 1)
        return wrap

    def _build_action_row(self) -> QFrame:
        row = QFrame()
        row.setObjectName("compactStatus")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)
        self.status_note = QLabel()
        self.status_note.setObjectName("mutedLabel")
        self.status_note.setWordWrap(True)
        self.primary_action = QPushButton("Review flagged ballots")
        self.primary_action.setObjectName("primaryButton")
        self.primary_action.clicked.connect(self._run_primary)
        self.secondary_action = QPushButton("Import image")
        self.secondary_action.setObjectName("ghostButton")
        self.secondary_action.clicked.connect(lambda: self.navigate.emit("scan"))
        layout.addWidget(self.status_note, 1)
        layout.addWidget(self.secondary_action)
        layout.addWidget(self.primary_action)
        self._primary_target = "review"
        return row

    def _build_overview(self) -> QHBoxLayout:
        charts = QHBoxLayout()
        charts.setSpacing(10)
        self.activity_card = Card()
        self.activity_card.layout.addWidget(
            SectionTitle("Ballots processed by hour", "Demonstration activity for this constituency")
        )
        self.activity_holder = QVBoxLayout()
        self.activity_card.layout.addLayout(self.activity_holder, 1)
        self.events_card = Card()
        self.events_card.layout.addWidget(SectionTitle("Latest events", "Most recent work at this location"))
        self.events_host = QVBoxLayout()
        self.events_host.setSpacing(4)
        self.events_card.layout.addLayout(self.events_host, 1)
        charts.addWidget(self.activity_card, 3)
        charts.addWidget(self.events_card, 2)
        return charts

    def _run_primary(self) -> None:
        self.navigate.emit(self._primary_target)

    def _replace_chart(self, holder: QVBoxLayout, widget: QWidget) -> None:
        while holder.count():
            item = holder.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        holder.addWidget(widget)

    def refresh(self) -> None:
        election = self.store.data["election"]
        self.location.apply_election(election)
        kind = election.get("data_kind", "none")
        has_data = kind in {"prototype_demo", "imported_session"}
        self.metrics.setVisible(has_data)
        self.candidate_card.setVisible(has_data)
        self.activity_card.setVisible(has_data)
        self.events_card.setVisible(has_data)
        self.empty.setVisible(not has_data)
        if not has_data:
            self.status_note.setText("Select Johor N.01 for the seeded demo, or import an image for this DUN.")
            self.primary_action.setText("Import ballot image")
            self._primary_target = "scan"
            self.secondary_action.setVisible(False)
            self.card_total.set_value("0")
            self.card_valid.set_value("0")
            self.card_flagged.set_value("0")
            return

        self.secondary_action.setVisible(True)
        stats = self.store.data["stats"]
        total = max(1, stats["total_processed"])
        pending = stats["pending_reviews"]
        self.card_total.set_value(format_number(stats["total_processed"]))
        self.card_total.set_hint(f"{election.get('batch')} · {election.get('dun')}")
        self.card_valid.set_value(format_number(stats["valid"]))
        self.card_valid.set_hint(f"{format_percent(stats['valid'] / total * 100)} of counted ballots")
        self.card_flagged.set_value(format_number(pending))
        self.card_flagged.set_hint("Officer verification still required")
        if pending:
            self.status_note.setText(
                f"{pending} ballot(s) need a decision before results can be treated as complete for {election.get('dun')}."
            )
            self.primary_action.setText(f"Review {pending} flagged ballot(s)")
            self._primary_target = "review"
            self.secondary_action.setText("Import image")
        else:
            self.status_note.setText(f"No flagged ballots waiting for {election.get('dun')}.")
            self.primary_action.setText("Open vote results")
            self._primary_target = "results"
            self.secondary_action.setText("Import image")

        records = self.store.data["candidates"]
        self.candidate_list.set_records(records, stats["valid"], limit=3, compact=True)
        self._replace_chart(self.activity_holder, activity_chart(self.store.data["activity"]))
        while self.events_host.count():
            item = self.events_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        events = self.store.data.get("processing_events", [])[:4]
        if not events:
            empty = QLabel("No events for this constituency yet.")
            empty.setObjectName("mutedLabel")
            self.events_host.addWidget(empty)
        else:
            for event in events:
                self.events_host.addWidget(EventRow(event))
        self.events_host.addStretch()
