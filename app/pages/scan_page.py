"""Scan Ballots: import dialog plus independent camera placeholder."""

from pathlib import Path

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.widgets.components import Card, NoticeBar, SectionTitle, StatusBadge, aligned_item, style_data_table
from app.widgets.location_bar import LocationBar

IMAGE_FILTER = "Ballot images (*.png *.jpg *.jpeg);;All files (*.*)"
ALLOWED = {".png", ".jpg", ".jpeg"}
QUEUED_RESULT = "Queued for officer review. The ballot was not marked valid and no vote was recognised."


def files_in_folder(directory: str) -> list[str]:
    folder = Path(directory)
    return [str(path) for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()) if path.is_file()]
STATUS_COLOR = {
    "Pending": "#94A3B8",
    "Processing": "#22D3EE",
    "Completed": "#34D399",
    "Failed": "#FB7185",
}


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
        self._batch_rows: list[dict] = []
        self._batch_index = 0
        self._batch_running = False
        self._batch_timer = QTimer(self)
        self._batch_timer.setSingleShot(True)
        self._batch_timer.timeout.connect(self._process_next_batch_row)
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
        workspace = QHBoxLayout()
        workspace.setSpacing(12)
        workspace.setAlignment(Qt.AlignmentFlag.AlignTop)
        import_card = self._build_import_card()
        import_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        workspace.addWidget(import_card, 2, Qt.AlignmentFlag.AlignTop)
        workspace.addWidget(self._build_preview_card(), 3)
        root.addLayout(workspace, 1)
        root.addWidget(self._build_camera_card())
        self.store.changed.connect(self._refresh_location)
        self._refresh_location()

    def _refresh_location(self) -> None:
        self.location.apply_election(self.store.data["election"])

    def _build_import_card(self) -> Card:
        card = Card()
        card.layout.addWidget(
            SectionTitle(
                "Import ballot images",
                "One image opens the preview dialog. Several images, or a folder, are processed one file at a time.",
            )
        )
        self.import_status = StatusBadge("No image selected", "neutral")
        card.layout.addWidget(self.import_status, 0, Qt.AlignmentFlag.AlignLeft)
        hint = QLabel(
            "PNG, JPG, or JPEG. Unsupported files stay in the batch as failed and do not stop the others."
        )
        hint.setObjectName("mutedLabel")
        hint.setWordWrap(True)
        card.layout.addWidget(hint)
        import_btn = QPushButton("Import Ballot Image")
        import_btn.setObjectName("primaryButton")
        import_btn.clicked.connect(self._choose_file)
        self.import_many_btn = QPushButton("Import images")
        self.import_many_btn.clicked.connect(self._choose_files)
        self.import_folder_btn = QPushButton("Import folder")
        self.import_folder_btn.clicked.connect(self._choose_folder)
        self._import_buttons = (import_btn, self.import_many_btn, self.import_folder_btn)
        for button in self._import_buttons:
            card.layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        self.batch_summary = QLabel("No batch yet")
        self.batch_summary.setObjectName("batchSummary")
        self.batch_summary.setWordWrap(True)
        card.layout.addWidget(self.batch_summary)
        self.retry_failed_btn = QPushButton("Retry failed")
        self.retry_failed_btn.setVisible(False)
        self.retry_failed_btn.clicked.connect(self._retry_failed)
        self.cancel_batch_btn = QPushButton("Cancel batch")
        self.cancel_batch_btn.setVisible(False)
        self.cancel_batch_btn.clicked.connect(self._cancel_batch)
        card.layout.addWidget(self.retry_failed_btn, 0, Qt.AlignmentFlag.AlignLeft)
        card.layout.addWidget(self.cancel_batch_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.last_import = QLabel("Last import: none")
        self.last_import.setObjectName("hintLabel")
        self.last_import.setWordWrap(True)
        card.layout.addWidget(self.last_import)
        self.review_now = QPushButton("Open review queue")
        self.review_now.setVisible(False)
        self.review_now.clicked.connect(lambda: self.navigate.emit("review"))
        card.layout.addWidget(self.review_now, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_preview_card(self) -> Card:
        card = Card()
        card.layout.addWidget(
            SectionTitle("Ballot preview", "Select a row to see that file. Each image is processed on its own.")
        )
        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setObjectName("batchTable")
        self.batch_table.setHorizontalHeaderLabels(["Filename", "Status", "Result"])
        style_data_table(self.batch_table)
        header = self.batch_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.batch_table.setMinimumHeight(132)
        self.batch_table.setMaximumHeight(220)
        self.batch_table.itemSelectionChanged.connect(self._on_batch_select)
        self.batch_table.setVisible(False)
        card.layout.addWidget(self.batch_table)
        self.page_preview = QLabel("No image selected")
        self.page_preview.setObjectName("previewFrame")
        self.page_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_preview.setWordWrap(True)
        self.page_preview.setMinimumHeight(220)
        self.page_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.layout.addWidget(self.page_preview, 1)
        details_caption = QLabel("File details")
        details_caption.setObjectName("fieldCaption")
        card.layout.addWidget(details_caption)
        self.preview_notes = QLabel(
            "No file is open. Import Ballot Image opens a dialog for one file. "
            "Import images or Import folder lists every file and processes each one separately."
        )
        self.preview_notes.setObjectName("mutedLabel")
        self.preview_notes.setWordWrap(True)
        card.layout.addWidget(self.preview_notes)
        return card

    def _build_camera_card(self) -> Card:
        card = Card()
        card.layout.addWidget(
            SectionTitle("AI camera / live capture", "Not available in this prototype")
        )
        body = QHBoxLayout()
        body.setSpacing(12)
        self.camera_preview = QLabel("Camera not connected\n\nNo live footage is shown here.")
        self.camera_preview.setObjectName("cameraPreview")
        self.camera_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.camera_preview.setWordWrap(True)
        self.camera_preview.setMinimumHeight(96)
        self.camera_preview.setMaximumHeight(120)
        self.camera_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        body.addWidget(self.camera_preview, 2)
        side = QVBoxLayout()
        side.setSpacing(8)
        self.camera_badge = StatusBadge("Not connected", "neutral")
        side.addWidget(self.camera_badge, 0, Qt.AlignmentFlag.AlignLeft)
        self.camera_message = QLabel(
            "This button only reports that no camera service is installed. It does not import files."
        )
        self.camera_message.setObjectName("hintLabel")
        self.camera_message.setWordWrap(True)
        side.addWidget(self.camera_message)
        connect_btn = QPushButton("Check camera connection")
        connect_btn.clicked.connect(self._connect_camera)
        side.addWidget(connect_btn, 0, Qt.AlignmentFlag.AlignLeft)
        body.addLayout(side, 3)
        card.layout.addLayout(body)
        return card

    def _show_file_preview(self, path: str, outcome: str) -> None:
        pixmap = QPixmap(path)
        name = Path(path).name
        if pixmap.isNull():
            self.page_preview.setPixmap(QPixmap())
            self.page_preview.setText("This file could not be opened as an image.")
            dims = "Dimensions unavailable"
        else:
            self.page_preview.setText("")
            scaled = pixmap.scaled(
                QSize(640, 360),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.page_preview.setPixmap(scaled)
            dims = f"{pixmap.width()} × {pixmap.height()} px"
        outcome_text = {
            "completed": "Queued for officer review. The ballot was not marked valid.",
            "cancelled": "Import cancelled. No ballot was classified.",
            "failed": "The file was not processed.",
            "review": "Queued for officer review.",
            "idle": "Dialog closed before processing.",
        }.get(outcome, "File selected.")
        self.preview_notes.setText(f"{name}\n{dims}\n\n{outcome_text}")

    def _choose_file(self) -> None:
        if self._batch_running:
            return
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
        self._show_file_preview(path, dialog._outcome)
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

    def _choose_files(self) -> None:
        if self._batch_running:
            return
        paths, _filter = QFileDialog.getOpenFileNames(self, "Import ballot images", "", IMAGE_FILTER)
        if not paths:
            return
        self.start_batch(paths)

    def _choose_folder(self) -> None:
        if self._batch_running:
            return
        directory = QFileDialog.getExistingDirectory(self, "Import ballot folder")
        if not directory:
            return
        paths = files_in_folder(directory)
        if not paths:
            QMessageBox.information(self, "Empty folder", "That folder does not contain any files.")
            return
        self.start_batch(paths)

    def start_batch(self, paths: list[str], *, retry: bool = False) -> None:
        """Queue each path and process it with the existing one-image workflow."""
        if self._batch_running:
            return
        if not retry:
            unique: list[str] = []
            seen: set[str] = set()
            for path in paths:
                key = str(Path(path))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(key)
            if not unique:
                return
            if self.store.data.get("imported"):
                self.store.clear_imported()
            self._batch_rows = [
                {"path": path, "name": Path(path).name, "status": "Pending", "detail": "Waiting to process."}
                for path in unique
            ]
        self._batch_index = 0
        self._batch_running = True
        self._render_batch()
        self._set_batch_controls(True)
        self.import_status.set_kind("info", "Processing")
        self._batch_timer.start(0)

    def _process_next_batch_row(self) -> None:
        if not self._batch_running:
            return
        while self._batch_index < len(self._batch_rows) and self._batch_rows[self._batch_index]["status"] != "Pending":
            self._batch_index += 1
        if self._batch_index >= len(self._batch_rows):
            self._finish_batch()
            return
        row = self._batch_rows[self._batch_index]
        row["status"] = "Processing"
        row["detail"] = "Running the existing import workflow."
        self._render_batch(select=self._batch_index)
        status, detail = self._process_image(row["path"])
        row["status"] = status
        row["detail"] = detail
        self._batch_index += 1
        self._render_batch(select=min(self._batch_index, len(self._batch_rows) - 1))
        self._batch_timer.start(0)

    def _process_image(self, path: str) -> tuple[str, str]:
        file_path = Path(path)
        if file_path.suffix.lower() not in ALLOWED:
            return "Failed", "Unsupported format. Use PNG, JPG, or JPEG."
        if not file_path.is_file():
            return "Failed", "File could not be found."
        pixmap = QPixmap(str(file_path))
        if pixmap.isNull():
            return "Failed", "This file could not be opened as an image."
        if not self.store.settings().get("demo_processing_mode", True):
            return (
                "Failed",
                "Cannot process. Demo Processing Mode is off, and no recognition engine is connected.",
            )
        before = int(self.store.data["stats"].get("pending_reviews", 0))
        try:
            self.store.add_imported([str(file_path)], notify=False)
            self.store.complete_import_processing(1, source_paths=[str(file_path)], notify=False)
        except Exception as exc:
            return "Failed", f"Processing error: {exc}"
        after = int(self.store.data["stats"].get("pending_reviews", 0))
        if after != before + 1:
            return "Failed", "The import workflow did not queue this image."
        return "Completed", QUEUED_RESULT

    def _finish_batch(self) -> None:
        self._batch_running = False
        self._batch_timer.stop()
        self._set_batch_controls(False)
        self._render_batch(select=0 if self._batch_rows else None)
        counts = self._batch_counts()
        if counts["failed"] and counts["completed"]:
            self.import_status.set_kind("warning", "Completed with failures")
            level = "warning"
        elif counts["failed"]:
            self.import_status.set_kind("error", "Could not process")
            level = "error"
        elif counts["completed"]:
            self.import_status.set_kind("warning", "Queued for review")
            level = "warning"
        else:
            self.import_status.set_kind("neutral", "No image selected")
            level = "info"
        self.review_now.setVisible(counts["completed"] > 0)
        if counts["total"]:
            self.last_import.setText(f"Last batch: {counts['total']} file(s)")
            self.store.message.emit(
                f"{counts['completed']} of {counts['total']} images queued for review. {counts['failed']} failed.",
                level,
            )

    def _retry_failed(self) -> None:
        if self._batch_running:
            return
        has_failed = any(row["status"] == "Failed" for row in self._batch_rows)
        has_pending = any(row["status"] == "Pending" for row in self._batch_rows)
        if not has_failed and not has_pending:
            return
        for row in self._batch_rows:
            if row["status"] == "Failed":
                row["status"] = "Pending"
                row["detail"] = "Waiting to retry."
        self.start_batch([], retry=True)

    def _cancel_batch(self) -> None:
        if not self._batch_running:
            return
        self._batch_running = False
        self._batch_timer.stop()
        self._set_batch_controls(False)
        counts = self._batch_counts()
        self.import_status.set_kind("neutral", "Cancelled")
        self.review_now.setVisible(counts["completed"] > 0)
        self._render_batch()
        self.store.message.emit(
            f"Batch stopped. {counts['completed']} completed, {counts['failed']} failed, {counts['pending']} still pending.",
            "warning",
        )

    def _batch_counts(self) -> dict[str, int]:
        counts = {"total": len(self._batch_rows), "completed": 0, "failed": 0, "pending": 0}
        for row in self._batch_rows:
            if row["status"] == "Completed":
                counts["completed"] += 1
            elif row["status"] == "Failed":
                counts["failed"] += 1
            elif row["status"] in {"Pending", "Processing"}:
                counts["pending"] += 1
        return counts

    def _set_batch_controls(self, running: bool) -> None:
        for button in self._import_buttons:
            button.setEnabled(not running)
        self.retry_failed_btn.setEnabled(not running)
        self.cancel_batch_btn.setVisible(running)

    def _render_batch(self, select: int | None = None) -> None:
        counts = self._batch_counts()
        if counts["total"]:
            self.batch_summary.setText(
                f"{counts['total']} images · {counts['completed']} completed · {counts['failed']} failed"
            )
        else:
            self.batch_summary.setText("No batch yet")
        if self._batch_running:
            self.retry_failed_btn.setVisible(False)
        elif counts["failed"]:
            self.retry_failed_btn.setText("Retry failed")
            self.retry_failed_btn.setVisible(True)
        elif counts["pending"]:
            self.retry_failed_btn.setText("Resume pending")
            self.retry_failed_btn.setVisible(True)
        else:
            self.retry_failed_btn.setVisible(False)
        self.batch_table.setVisible(bool(self._batch_rows))
        self.batch_table.blockSignals(True)
        self.batch_table.setRowCount(len(self._batch_rows))
        for index, row in enumerate(self._batch_rows):
            name_item = aligned_item(row["name"])
            name_item.setToolTip(row["path"])
            status_item = aligned_item(row["status"])
            status_item.setForeground(QColor(STATUS_COLOR.get(row["status"], "#F1F5F9")))
            detail_item = aligned_item(row["detail"])
            detail_item.setToolTip(row["detail"])
            self.batch_table.setItem(index, 0, name_item)
            self.batch_table.setItem(index, 1, status_item)
            self.batch_table.setItem(index, 2, detail_item)
        self.batch_table.resizeRowsToContents()
        self.batch_table.blockSignals(False)
        if select is not None and self._batch_rows:
            self.batch_table.selectRow(select)
        elif self._batch_rows and self.batch_table.currentRow() < 0:
            self.batch_table.selectRow(0)

    def _on_batch_select(self) -> None:
        row_index = self.batch_table.currentRow()
        if not (0 <= row_index < len(self._batch_rows)):
            return
        row = self._batch_rows[row_index]
        self._show_batch_preview(row["path"], row["detail"])

    def _show_batch_preview(self, path: str, detail: str) -> None:
        file_path = Path(path)
        pixmap = QPixmap(str(file_path)) if file_path.is_file() else QPixmap()
        if pixmap.isNull():
            self.page_preview.setPixmap(QPixmap())
            self.page_preview.setText(file_path.name if file_path.name else "No image selected")
            dims = "Preview unavailable"
        else:
            self.page_preview.setText("")
            scaled = pixmap.scaled(
                QSize(640, 280),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.page_preview.setPixmap(scaled)
            dims = f"{pixmap.width()} × {pixmap.height()} px"
        self.preview_notes.setText(f"{file_path.name}\n{dims}\n\n{detail}")

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
