"""Prototype audit log with search, filters, detail, and CSV export."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.utils import format_number, format_timestamp
from app.services.export_service import export_audit_csv
from app.widgets.components import Card, NoticeBar, SectionTitle, StatCard


class AuditPage(QScrollArea):
    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
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

        description = QLabel(
            "View a record of important actions performed in BallotVision, such as ballot processing, "
            "review decisions, and result exports. This helps election officers track what happened and when, "
            "and supports transparency and accountability."
        )
        description.setWordWrap(True)
        description.setObjectName("mutedLabel")
        root.addWidget(description)
        root.addWidget(
            NoticeBar(
                "This page currently shows demonstration and prototype events. It is not an official SPR election record.",
                "warning",
            )
        )

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.total = StatCard("Activities", "0", "All recorded events", icon="about")
        self.reviews = StatCard("Reviews logged", "0", "Officer decisions", icon="shield", icon_color="#34D399")
        stats.addWidget(self.total)
        stats.addWidget(self.reviews)
        stats.addStretch()
        root.addLayout(stats)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search action, user, or ID")
        self.search.textChanged.connect(self.refresh)
        self.type_filter = QComboBox()
        self.type_filter.addItems(
            [
                "All types",
                "Image Import",
                "Processing Simulation",
                "Flagged Ballot",
                "Review Decision",
                "CSV Export",
                "System Event",
            ]
        )
        self.type_filter.currentTextChanged.connect(lambda _text: self.refresh())
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All statuses", "Completed", "Warning"])
        self.status_filter.currentTextChanged.connect(lambda _text: self.refresh())
        export_btn = QPushButton("Export Audit Log")
        export_btn.setObjectName("primaryButton")
        export_btn.clicked.connect(self._export)
        filters.addWidget(self.search, 2)
        filters.addWidget(self.type_filter)
        filters.addWidget(self.status_filter)
        filters.addWidget(export_btn)
        root.addLayout(filters)

        split = QHBoxLayout()
        split.setSpacing(12)
        table_card = Card()
        table_card.layout.addWidget(SectionTitle("Activity", "Select a row to read the full record"))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Timestamp", "Activity ID", "User", "Action", "Related Ballot / Batch", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._show_detail)
        table_card.layout.addWidget(self.table, 1)
        split.addWidget(table_card, 3)

        detail = Card()
        detail.setObjectName("detailPanel")
        detail.layout.addWidget(SectionTitle("Record detail", "Full text of the selected event"))
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Select an activity to view details.")
        detail.layout.addWidget(self.detail, 1)
        split.addWidget(detail, 2)
        root.addLayout(split, 1)

        self.empty = QLabel("")
        self.empty.setObjectName("mutedLabel")
        root.addWidget(self.empty)

        self.store.changed.connect(self.refresh)
        self.refresh()

    def _visible_events(self) -> list[dict]:
        query = self.search.text().strip().lower()
        type_name = self.type_filter.currentText()
        status_name = self.status_filter.currentText()
        rows = []
        for event in self.store.data["audit"]:
            if type_name != "All types" and event["type"] != type_name:
                continue
            if status_name != "All statuses" and event["status"] != status_name:
                continue
            blob = f"{event['id']} {event['user']} {event['action']} {event['related']} {event['detail']}".lower()
            if query and query not in blob:
                continue
            rows.append(event)
        return rows

    def refresh(self) -> None:
        events = self.store.data["audit"]
        self.total.set_value(format_number(len(events)))
        reviews = sum(1 for event in events if event["type"] == "Review Decision")
        self.reviews.set_value(format_number(reviews))

        rows = self._visible_events()
        time_format = self.store.settings().get("time_format", "24-hour")
        self.table.setRowCount(len(rows))
        self.empty.setText("" if rows else "No activity records match the current search and filters.")
        for index, event in enumerate(rows):
            values = [
                format_timestamp(event["time"], time_format),
                event["id"],
                event["user"],
                event["action"],
                event["related"],
                event["status"],
            ]
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(value))
        if rows:
            self.table.selectRow(0)
            self._show_detail()
        else:
            self.detail.clear()

    def _show_detail(self) -> None:
        rows = self._visible_events()
        row = self.table.currentRow()
        if not (0 <= row < len(rows)):
            return
        event = rows[row]
        time_format = self.store.settings().get("time_format", "24-hour")
        self.detail.setPlainText(
            "\n".join(
                [
                    f"Activity ID: {event['id']}",
                    f"Timestamp: {format_timestamp(event['time'], time_format)}",
                    f"User: {event['user']}",
                    f"Action: {event['action']}",
                    f"Type: {event['type']}",
                    f"Related: {event['related']}",
                    f"Status: {event['status']}",
                    "",
                    event["detail"],
                    "",
                    "This record belongs to the BallotVision UI prototype.",
                ]
            )
        )

    def _export(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Export prototype audit log",
            "ballotvision_audit_prototype.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        export_audit_csv(
            path,
            self._visible_events(),
            self.store.settings().get("time_format", "24-hour"),
        )
        self.store.record_export("audit log CSV", path)
