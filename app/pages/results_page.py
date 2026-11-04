"""Constituency-scoped unofficial candidate results."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.candidates import leading_record
from app.core.utils import format_number, format_percent
from app.services.export_service import export_results_csv, export_results_summary
from app.widgets.candidate_rows import CandidateList, sort_candidates
from app.widgets.charts import candidate_bar_chart
from app.widgets.components import Card, EmptyState, NoticeBar, SectionTitle, StatCard
from app.widgets.location_bar import LocationBar


class ResultsPage(QWidget):
    navigate = Signal(str)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setObjectName("pageBody")
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 8, 24, 10)
        self.root.setSpacing(6)

        self.root.addWidget(
            NoticeBar(
                "Unofficial demonstration results. Percentages use valid votes. This is not an SPR return.",
                "error",
            )
        )
        self.location = LocationBar()
        self.location.location_changed.connect(self.store.set_demo_location)
        self.root.addWidget(self.location)

        self.empty = EmptyState(
            "No results for this constituency",
            "Totals are not copied between DUN seats. Open Johor N.01 Buloh Kasap for the seeded demo, or import ballots here.",
            "Import ballot image",
        )
        self.empty.action.clicked.connect(lambda: self.navigate.emit("scan"))
        self.root.addWidget(self.empty)

        self.content = QWidget()
        content = QVBoxLayout(self.content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(6)

        self.stats_wrap = QWidget()
        stats = QGridLayout(self.stats_wrap)
        stats.setContentsMargins(0, 0, 0, 0)
        stats.setHorizontalSpacing(6)
        stats.setVerticalSpacing(0)
        self.total = StatCard("Ballots counted", "0", "This constituency only", icon="layers")
        self.valid = StatCard("Valid votes", "0", "Used for percentages", icon="shield", icon_color="#34D399")
        self.rejected = StatCard("Rejected", "0", "Not in percentages", icon="alert", icon_color="#FB7185")
        self.candidate_count = StatCard("Candidates", "0", "Fictional demo roster", icon="about")
        self.leader = StatCard("Leading", "—", "Unofficial only", icon="shield", icon_color="#22D3EE")
        for column, card in enumerate((self.total, self.valid, self.rejected, self.candidate_count, self.leader)):
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.layout.setContentsMargins(10, 8, 10, 8)
            card.layout.setSpacing(4)
            stats.addWidget(card, 0, column)
        content.addWidget(self.stats_wrap)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        self.review_action = QPushButton("Review remaining flags")
        self.review_action.clicked.connect(lambda: self.navigate.emit("review"))
        export_csv = QPushButton("Export CSV")
        export_csv.setObjectName("primaryButton")
        export_csv.clicked.connect(self._export_csv)
        export_summary = QPushButton("Export summary")
        export_summary.clicked.connect(self._export_summary)
        actions.addWidget(self.review_action)
        actions.addWidget(export_csv)
        actions.addWidget(export_summary)
        actions.addStretch()
        note = QLabel("Exports stay unofficial. No official winner is declared.")
        note.setObjectName("mutedLabel")
        actions.addWidget(note)
        content.addLayout(actions)

        split = QHBoxLayout()
        split.setSpacing(8)
        list_card = Card()
        list_card.layout.setContentsMargins(10, 8, 10, 8)
        list_card.layout.setSpacing(4)
        list_card.layout.addWidget(
            SectionTitle("Candidates", "Highest votes first · fictional names · % of valid votes")
        )
        self.candidate_list = CandidateList(scrollable=True, dense=True)
        list_card.layout.addWidget(self.candidate_list, 1)
        split.addWidget(list_card, 3)
        self.bar_card = Card()
        self.bar_card.layout.setContentsMargins(10, 8, 10, 8)
        self.bar_card.layout.setSpacing(4)
        self.bar_card.layout.addWidget(SectionTitle("Vote comparison", "Updates when Negeri or DUN changes"))
        self.bar_holder = QVBoxLayout()
        self.bar_holder.setContentsMargins(0, 0, 0, 0)
        self.bar_holder.setSpacing(0)
        self.bar_card.layout.addLayout(self.bar_holder, 1)
        split.addWidget(self.bar_card, 2)
        content.addLayout(split, 1)
        self.root.addWidget(self.content, 1)

        self.store.changed.connect(self.refresh)
        self.refresh()

    def _replace(self, holder: QVBoxLayout, widget: QWidget) -> None:
        while holder.count():
            item = holder.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        holder.addWidget(widget)

    def refresh(self) -> None:
        election = self.store.data.get("election", {})
        self.location.apply_election(election)
        kind = election.get("data_kind", "none")
        has_data = kind in {"prototype_demo", "imported_session"}
        self.empty.setVisible(not has_data)
        self.content.setVisible(has_data)
        if not has_data:
            return
        stats = self.store.data["stats"]
        records = sort_candidates(self.store.data["candidates"])
        valid = stats["valid"]
        pending = stats["pending_reviews"]
        self.total.set_value(format_number(stats["total_processed"]))
        self.valid.set_value(format_number(valid))
        self.rejected.set_value(format_number(stats["rejected"]))
        self.candidate_count.set_value(str(len(records)))
        self.review_action.setVisible(pending > 0)
        self.review_action.setText(f"Review {pending} flagged ballot(s)")
        leader = leading_record(records) if pending == 0 else None
        if leader:
            share = leader["vote_count"] / valid * 100 if valid else 0
            self.leader.set_value(leader["candidate_name"])
            self.leader.set_hint(f"{format_percent(share)} of valid votes · unofficial")
        elif pending:
            self.leader.set_value("Not declared")
            self.leader.set_hint("Reviews outstanding")
        else:
            self.leader.set_value("Not declared")
            self.leader.set_hint("Incomplete or tied")
        self.candidate_list.set_records(records, valid)
        self._replace(self.bar_holder, candidate_bar_chart(records))

    def _export_csv(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export unofficial results",
            "ballotvision_simulated_results.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        data = dict(self.store.data)
        data["candidates"] = sort_candidates(self.store.data["candidates"])
        export_results_csv(path, data)
        self.store.record_export("results CSV", path)

    def _export_summary(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export unofficial summary",
            "ballotvision_simulated_summary.txt",
            "Text files (*.txt)",
        )
        if not path:
            return
        data = dict(self.store.data)
        data["candidates"] = sort_candidates(self.store.data["candidates"])
        export_results_summary(path, data)
        self.store.record_export("results summary", path)
