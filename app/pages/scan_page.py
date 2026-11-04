"""Scan Ballots: import dialog plus independent camera placeholder."""

from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.widgets.components import Card, NoticeBar, SectionTitle, StatusBadge
from app.widgets.location_bar import LocationBar

IMAGE_FILTER = "Ballot images (*.png *.jpg *.jpeg);;All files (*.*)"
ALLOWED = {".png", ".jpg", ".jpeg"}


class ImportBallotDialog(QDialog):
    def __init__(self, store, image_path: str, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.image_path = image_path
        self._progress = 0
        self._outcome = "idle"
        self.setWindowTitle("Imported Ballot Image")
        self.setModal(True)
        self.setMinimumSize(720, 560)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(
            SectionTitle(
                "Imported Ballot Image",
                "Check the file, then click Process Image. Selecting a file does not start recognition.",
            )
        )
        layout.addWidget(
            NoticeBar("Demonstration processing — recognition engine not connected", "warning")
        )

        self.preview = QLabel()
        self.preview.setObjectName("previewFrame")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(280)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.preview, 1)

        pixmap = QPixmap(image_path)
        name = Path(image_path).name
        if pixmap.isNull():
            self.preview.setText("This file could not be opened as an image.")
            dims = "unavailable"
            self._readable = False
        else:
            self._readable = True
            dims = f"{pixmap.width()} × {pixmap.height()} px"
            scaled = pixmap.scaled(
                QSize(680, 320),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview.setPixmap(scaled)
        self.meta = QLabel(f"{name}\n{dims}")
        self.meta.setObjectName("mutedLabel")
        layout.addWidget(self.meta)

        self.status = QLabel("Ready. Nothing has been processed yet.")
        self.status.setObjectName("mutedLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        layout.addWidget(self.progress)

        buttons = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel)
        self.process_btn = QPushButton("Process Image")
        self.process_btn.setObjectName("primaryButton")
        self.process_btn.setEnabled(self._readable)
        self.process_btn.clicked.connect(self._start)
        self.review_btn = QPushButton("Review flagged ballot")
        self.review_btn.setObjectName("primaryButton")
        self.review_btn.setVisible(False)
        self.review_btn.clicked.connect(self._open_review)
        buttons.addWidget(self.cancel_btn)
        buttons.addStretch()
        buttons.addWidget(self.process_btn)
        buttons.addWidget(self.review_btn)
        layout.addLayout(buttons)

    def _start(self) -> None:
        if self.timer.isActive():
            return
        if not self.store.settings().get("demo_processing_mode", True):
            self.status.setText(
                "Cannot process. Demo Processing Mode is off, and no recognition engine is connected."
            )
            self._outcome = "failed"
            self.process_btn.setEnabled(False)
            return
        self.store.add_imported([self.image_path])
        self._progress = 0
        self.progress.setValue(0)
        self.process_btn.setEnabled(False)
        self.status.setText("Demonstration processing started. This is not AI recognition.")
        self.timer.start(70)

    def _tick(self) -> None:
        if self._outcome == "completed":
            self.timer.stop()
            return
        self._progress += 2
        self.progress.setValue(min(100, self._progress))
        messages = {
            12: "Reading the image…",
            40: "Creating an inspection record…",
            72: "Sending the ballot to the review queue…",
            90: "Writing the prototype audit entry…",
        }
        if self._progress in messages:
            self.status.setText(messages[self._progress])
        if self._progress >= 100:
            self.timer.stop()
            self._outcome = "completed"
            self.status.setText(
                "Queued for officer review. The ballot was not marked valid and no vote was recognised."
            )
            self.store.complete_import_processing(1)
            self.process_btn.setVisible(False)
            self.review_btn.setVisible(True)
            self.cancel_btn.setText("Close")

    def _cancel(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self._outcome = "cancelled"
            self.store.complete_import_processing(0, cancelled=True)
            self.status.setText("Cancelled. No ballot was classified.")
        self.reject() if self._outcome in {"idle", "cancelled", "failed"} else self.accept()

    def _open_review(self) -> None:
        self._outcome = "review"
        self.accept()


class ScanPage(QWidget):
    navigate = Signal(str)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.setObjectName("pageBody")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 12, 24, 16)
        root.setSpacing(10)
        root.addWidget(
            NoticeBar(
                "Imported images are assigned to the constituency selected below. Camera capture is a separate, future workflow.",
                "info",
            )
        )
        self.location = LocationBar()
        self.location.location_changed.connect(self.store.set_demo_location)
        root.addWidget(self.location)
        columns = QHBoxLayout()
        columns.setSpacing(12)
        columns.addWidget(self._build_import_card(), 3)
        columns.addWidget(self._build_camera_card(), 2)
        root.addLayout(columns, 1)
        self.store.changed.connect(self._refresh_location)
        self._refresh_location()

    def _refresh_location(self) -> None:
        self.location.apply_election(self.store.data["election"])

    def _build_import_card(self) -> Card:
        card = Card()
        card.layout.addWidget(
            SectionTitle("Import ballot image", "Use a PNG, JPG, or JPEG already captured on this computer.")
        )
        self.import_status = StatusBadge("No image selected", "neutral")
        card.layout.addWidget(self.import_status, 0, Qt.AlignmentFlag.AlignLeft)
        hint = QLabel(
            "The preview dialog opens after you choose a file. Processing starts only when you click Process Image."
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        card.layout.addWidget(hint)
        import_btn = QPushButton("Import Ballot Image")
        import_btn.setObjectName("primaryButton")
        import_btn.clicked.connect(self._choose_file)
        card.layout.addWidget(import_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.last_import = QLabel("Last import: none")
        self.last_import.setObjectName("hintLabel")
        self.last_import.setWordWrap(True)
        card.layout.addWidget(self.last_import)
        self.review_now = QPushButton("Open review queue")
        self.review_now.setVisible(False)
        self.review_now.clicked.connect(lambda: self.navigate.emit("review"))
        card.layout.addWidget(self.review_now, 0, Qt.AlignmentFlag.AlignLeft)
        card.layout.addStretch()
        return card

    def _build_camera_card(self) -> Card:
        card = Card()
        card.layout.addWidget(
            SectionTitle("AI camera / live capture", "Not available in this prototype")
        )
        self.camera_preview = QLabel("Camera not connected\n\nNo live footage is shown here.")
        self.camera_preview.setObjectName("cameraPreview")
        self.camera_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_preview.setWordWrap(True)
        self.camera_preview.setMinimumHeight(180)
        self.camera_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.layout.addWidget(self.camera_preview, 1)
        self.camera_badge = StatusBadge("Not connected", "neutral")
        card.layout.addWidget(self.camera_badge, 0, Qt.AlignmentFlag.AlignLeft)
        self.camera_message = QLabel(
            "This button only reports that no camera service is installed. It does not import files."
        )
        self.camera_message.setObjectName("hintLabel")
        self.camera_message.setWordWrap(True)
        card.layout.addWidget(self.camera_message)
        connect_btn = QPushButton("Check camera connection")
        connect_btn.clicked.connect(self._connect_camera)
        card.layout.addWidget(connect_btn, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _choose_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Import ballot image", "", IMAGE_FILTER)
        if not path:
            return
        if Path(path).suffix.lower() not in ALLOWED:
            QMessageBox.warning(self, "Unsupported file", "Use PNG, JPG, or JPEG.")
            return
        if self.store.data.get("imported"):
            self.store.clear_imported()
        dialog = ImportBallotDialog(self.store, path, self)
        result = dialog.exec()
        self.last_import.setText(f"Last file: {Path(path).name}")
        if dialog._outcome == "completed":
            self.import_status.set_kind("warning", "Queued for review")
            self.review_now.setVisible(True)
        elif dialog._outcome == "cancelled":
            self.import_status.set_kind("neutral", "Cancelled")
            self.review_now.setVisible(False)
        elif dialog._outcome == "failed":
            self.import_status.set_kind("error", "Could not process")
            self.review_now.setVisible(False)
        elif dialog._outcome == "review":
            self.import_status.set_kind("warning", "Queued for review")
            self.review_now.setVisible(True)
            self.navigate.emit("review")
        elif result:
            self.import_status.set_kind("info", "Closed")

    def _connect_camera(self) -> None:
        self.camera_badge.set_kind("warning", "Not available")
        self.camera_preview.setText("Camera integration pending\n\nNo capture device was opened.")
        self.camera_message.setText(
            "No camera driver is linked to BallotVision. Import a ballot image to continue."
        )
        self.store.add_audit(
            user="Sahira",
            action="Checked camera connection",
            related="CAMERA",
            event_type="System Event",
            status="Warning",
            detail="Camera integration is pending. No device was opened.",
        )
        self.store.message.emit("Camera is not connected. Use Import Ballot Image instead.", "warning")
