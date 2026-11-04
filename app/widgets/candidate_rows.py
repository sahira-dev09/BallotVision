"""Candidate rows. Dashboard uses the original card layout; Vote Results uses a dense list."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.utils import format_number, format_percent
from app.widgets.charts import color_for_candidate
from app.widgets.components import StatusBadge
from app.widgets.portraits import PortraitLabel

def _match_card_surface(widget) -> None:
    widget.setAutoFillBackground(False)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


def sort_candidates(records: list[dict]) -> list[dict]:
    return sorted(
        records,
        key=lambda item: (-int(item.get("vote_count", 0)), item.get("ballot_position", 99)),
    )


class VoteShareBar(QProgressBar):
    def __init__(self, dense: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setRange(0, 1000)
        self.setTextVisible(False)
        self.setFixedHeight(5 if dense else 8)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("voteShareBarDense" if dense else "voteShareBar")


class CandidateRow(QFrame):
    def __init__(
        self,
        record: dict,
        valid_votes: int,
        compact: bool = False,
        dense: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        votes = int(record.get("vote_count", 0))
        share = (votes / valid_votes * 100) if valid_votes else 0
        if dense:
            self._build_dense(record, votes, share)
        else:
            self._build_card(record, votes, share, compact)

    def _status_badge(self, record: dict):
        status = record.get("result_status", "none")
        if status == "leading":
            return StatusBadge("Leading (unofficial)", "info")
        if status == "tied":
            return StatusBadge("Tied (unofficial)", "warning")
        return None

    def _build_card(self, record: dict, votes: int, share: float, compact: bool) -> None:
        self.setObjectName("candidateRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        size = 36 if compact else 48
        layout.addWidget(PortraitLabel(record, size), 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(record.get("candidate_name", "—"))
        name.setObjectName("candidateName")
        meta = QLabel(
            f"{record.get('candidate_id')}  ·  Pos {record.get('ballot_position')}  ·  {record.get('party_name')}"
        )
        meta.setObjectName("hintLabel")
        text.addWidget(name)
        text.addWidget(meta)
        layout.addLayout(text, 2)

        numbers = QVBoxLayout()
        numbers.setSpacing(2)
        count = QLabel(format_number(votes))
        count.setObjectName("candidateVotes")
        percent = QLabel(f"{format_percent(share)} of valid votes")
        percent.setObjectName("hintLabel")
        bar = VoteShareBar()
        bar.setValue(int(share * 10))
        _tint_share(bar, color_for_candidate(record).name())
        numbers.addWidget(count)
        numbers.addWidget(percent)
        numbers.addWidget(bar)
        layout.addLayout(numbers, 1)

        badge = self._status_badge(record)
        if badge is not None:
            layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

    def _build_dense(self, record: dict, votes: int, share: float) -> None:
        self.setObjectName("candidateRowDense")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(PortraitLabel(record, 36), 0, Qt.AlignmentFlag.AlignVCenter)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        name = QLabel(record.get("candidate_name", "—"))
        name.setObjectName("candidateName")
        party = QLabel(record.get("party_name") or "Independent (Demo)")
        party.setObjectName("hintLabel")
        text.addWidget(name)
        text.addWidget(party)
        row.addLayout(text, 1)

        numbers = QVBoxLayout()
        numbers.setContentsMargins(0, 0, 0, 0)
        numbers.setSpacing(0)
        count = QLabel(format_number(votes))
        count.setObjectName("candidateVotes")
        count.setAlignment(Qt.AlignmentFlag.AlignRight)
        percent = QLabel(format_percent(share))
        percent.setObjectName("hintLabel")
        percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        percent.setToolTip("Percentage of valid votes")
        numbers.addWidget(count)
        numbers.addWidget(percent)
        row.addLayout(numbers, 0)

        badge = self._status_badge(record)
        if badge is not None:
            row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)

        root.addLayout(row)
        bar = VoteShareBar(dense=True)
        bar.setValue(int(share * 10))
        _tint_share(bar, color_for_candidate(record).name())
        root.addWidget(bar)


def _tint_share(bar: VoteShareBar, color: str) -> None:
    name = bar.objectName()
    radius = "3px" if name == "voteShareBarDense" else "4px"
    bar.setStyleSheet(
        f"#{name} {{ background: #1B2940; border: none; border-radius: {radius}; }}"
        f"#{name}::chunk {{ background: {color}; border-radius: {radius}; }}"
    )


class CandidateList(QWidget):
    def __init__(self, parent=None, scrollable: bool = False, dense: bool = False) -> None:
        super().__init__(parent)
        self.dense = dense
        self.setObjectName("candidateList")
        _match_card_surface(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._inner = QWidget()
        self._inner.setObjectName("candidateList")
        _match_card_surface(self._inner)
        self.host = QVBoxLayout(self._inner)
        self.host.setContentsMargins(0, 0, 0, 0)
        self.host.setSpacing(2 if dense else 6)
        if scrollable:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            scroll = QScrollArea()
            scroll.setObjectName("candidateListScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            _match_card_surface(scroll)
            _match_card_surface(scroll.viewport())
            scroll.setWidget(self._inner)
            outer.addWidget(scroll, 1)
        else:
            outer.addWidget(self._inner)

    def set_records(self, records: list[dict], valid_votes: int, limit: int | None = None, compact: bool = False) -> None:
        while self.host.count():
            item = self.host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        ordered = sort_candidates(records)
        shown = ordered if limit is None else ordered[:limit]
        if not shown:
            empty = QLabel("No candidate records for this constituency.")
            empty.setObjectName("mutedLabel")
            self.host.addWidget(empty)
            return
        for record in shown:
            self.host.addWidget(
                CandidateRow(record, valid_votes, compact=compact, dense=self.dense)
            )
        if limit is not None and len(ordered) > limit:
            extra = QLabel(f"Showing {limit} of {len(ordered)} candidates. Open Vote Results for the full list.")
            extra.setObjectName("hintLabel")
            extra.setWordWrap(True)
            self.host.addWidget(extra)
        if self.dense:
            self.host.addStretch()
