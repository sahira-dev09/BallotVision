"""Demonstration settings with save, reset, and clear-data actions."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import APP_BRAND_TAG, APP_NAME, APP_SUBTITLE, APP_VERSION
from app.widgets.components import Card, NoticeBar, SectionTitle


class SettingsPage(QScrollArea):
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

        root.addWidget(
            NoticeBar("Settings apply to this prototype on this computer. They do not change any official SPR system.", "info")
        )

        top_actions = QHBoxLayout()
        save = QPushButton("Save Settings")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        reset = QPushButton("Reset to Defaults")
        reset.clicked.connect(self._reset)
        top_actions.addWidget(save)
        top_actions.addWidget(reset)
        top_actions.addStretch()
        root.addLayout(top_actions)

        columns = QGridLayout()
        columns.setHorizontalSpacing(10)
        columns.setVerticalSpacing(10)

        general = Card()
        general.layout.addWidget(SectionTitle("Display", "How timestamps appear in the audit log"))
        general_form = QFormLayout()
        self.theme = QLineEdit()
        self.theme.setReadOnly(True)
        self.time_format = QComboBox()
        self.time_format.addItems(["24-hour", "12-hour"])
        general_form.addRow("Theme", self.theme)
        general_form.addRow("Date and time", self.time_format)
        general.layout.addLayout(general_form)

        processing = Card()
        processing.layout.addWidget(
            SectionTitle("Processing", "OCR is available. This switch controls the review queue.")
        )
        self.demo_mode = QCheckBox("Allow demonstration processing")
        processing.layout.addWidget(self.demo_mode)
        hint = QLabel(
            "Turn this off to block Process Image. A clear single mark on a registered candidate can be counted. Unclear ballots stay in the review queue."
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        processing.layout.addWidget(hint)

        review = Card()
        review.layout.addWidget(SectionTitle("Review queue", "How the officer confirms a decision"))
        self.require_confirm = QCheckBox("Ask for confirmation before submitting a decision")
        review.layout.addWidget(self.require_confirm)
        review_form = QFormLayout()
        self.default_filter = QComboBox()
        self.default_filter.addItems(["Pending Review", "Reviewed", "All"])
        review_form.addRow("Show first", self.default_filter)
        review.layout.addLayout(review_form)

        data = Card()
        data.layout.addWidget(SectionTitle("Demo data", "Reset sample ballots without changing these settings"))
        clear = QPushButton("Clear demo data")
        clear.setObjectName("dangerButton")
        clear.clicked.connect(self._clear_data)
        data.layout.addWidget(clear, 0, Qt.AlignmentFlag.AlignLeft)

        about = Card()
        about.layout.addWidget(SectionTitle("About", "Project identity"))
        about.layout.addWidget(QLabel(f"{APP_NAME}  ·  {APP_BRAND_TAG}  ·  Version {APP_VERSION}"))
        stack = QLabel("Python + PySide6")
        stack.setObjectName("mutedLabel")
        about.layout.addWidget(stack)
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("hintLabel")
        subtitle.setWordWrap(True)
        about.layout.addWidget(subtitle)

        columns.addWidget(general, 0, 0)
        columns.addWidget(processing, 0, 1)
        columns.addWidget(review, 1, 0)
        columns.addWidget(data, 1, 1)
        columns.addWidget(about, 2, 0, 1, 2)
        columns.setColumnStretch(0, 1)
        columns.setColumnStretch(1, 1)
        root.addLayout(columns, 1)

        self.store.changed.connect(self.load_from_store)
        self.load_from_store()

    def load_from_store(self) -> None:
        settings = self.store.settings()
        self.theme.setText(settings.get("theme_name", "Dark Navy"))
        self.time_format.setCurrentText(settings.get("time_format", "24-hour"))
        self.demo_mode.setChecked(bool(settings.get("demo_processing_mode", True)))
        self.require_confirm.setChecked(bool(settings.get("require_reviewer_confirmation", True)))
        self.default_filter.setCurrentText(settings.get("default_review_filter", "Pending Review"))

    def _collect(self) -> dict:
        current = self.store.settings()
        return {
            "app_name": APP_NAME,
            "theme_name": "Dark Navy",
            "time_format": self.time_format.currentText(),
            "demo_processing_mode": self.demo_mode.isChecked(),
            "confidence_threshold": current.get("confidence_threshold", 85),
            "require_reviewer_confirmation": self.require_confirm.isChecked(),
            "default_review_filter": self.default_filter.currentText(),
            "export_format": current.get("export_format", "CSV"),
            "demo_negeri": current.get("demo_negeri", "Johor"),
            "demo_dun_code": current.get("demo_dun_code", "N.01"),
            "demo_dun_name": current.get("demo_dun_name", "Buloh Kasap"),
        }

    def _save(self) -> None:
        self.store.data["settings"].update(self._collect())
        self.store.save_settings()

    def _reset(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset settings",
            "Restore every setting to the original demonstration defaults?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.reset_settings()
            self.load_from_store()

    def _clear_data(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear demo data",
            "Reset sample ballots, results, imported images, and the prototype audit log?\n\n"
            "Saved settings will be kept.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.store.reset_demo_data()
