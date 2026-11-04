"""Scan Ballots: import dialog plus independent camera placeholder."""

import threading
import time
from pathlib import Path

from PySide6.QtCore import QSize, QThread, QTimer, Qt, Signal
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

from app.services.mark_recognition import (
    NOT_DETECTED,
    REASON_UNAVAILABLE,
    STATUS_UNAVAILABLE,
    MarkResult,
    recognize_marks,
)
from app.services.ocr_service import (
    INSPECTION_LIMIT_SECONDS,
    OCR_TIMEOUT_MESSAGE,
    install_ocr_process_tracking,
    read_ballot_image,
)
from app.services.thread_cleanup import (
    is_shutting_down,
    register_shutdown_hook,
    retain_until_finished,
    unregister_shutdown_hook,
)
from app.widgets.components import Card, NoticeBar, SectionTitle, StatusBadge, aligned_item, style_data_table
from app.widgets.ocr_panel import OcrDetailPanel, fields_from_inspection

IMAGE_FILTER = "Ballot images (*.png *.jpg *.jpeg);;All files (*.*)"
ALLOWED = {".png", ".jpg", ".jpeg"}
QUEUED_RESULT = "Added to the officer review queue. No vote was counted."
COUNTED_RESULT = "Provisional vote recorded for one clear mark. This ballot was counted once."
# QPainter is not safe on two threads at once. Inspections already run one at a time
# in a batch; this also covers a dialog worker overlapping that batch.
_INSPECT_LOCK = threading.Lock()


class InspectWorker(QThread):
    """OCR, location matching, and mark recognition for one image."""

    completed = Signal(object)

    def __init__(self, image_path: str, parent=None) -> None:
        super().__init__(parent)
        self.image_path = image_path

    def run(self) -> None:  # noqa: N802
        install_ocr_process_tracking()
        deadline = time.monotonic() + INSPECTION_LIMIT_SECONDS
        with _INSPECT_LOCK:
            if self.isInterruptionRequested():
                return
            reading = read_ballot_image(self.image_path, deadline=deadline)
            if self.isInterruptionRequested():
                return
            if reading.ocr.error == OCR_TIMEOUT_MESSAGE or time.monotonic() >= deadline:
                marks = MarkResult(
                    STATUS_UNAVAILABLE,
                    NOT_DETECTED,
                    "",
                    0,
                    0,
                    REASON_UNAVAILABLE,
                    OCR_TIMEOUT_MESSAGE,
                )
            else:
                marks = recognize_marks(self.image_path, deadline=deadline)
            if self.isInterruptionRequested():
                return
            self.completed.emit((reading, marks))


def files_in_folder(directory: str) -> list[str]:
    folder = Path(directory)
    return [str(path) for path in sorted(folder.iterdir(), key=lambda item: item.name.lower()) if path.is_file()]
STATUS_COLOR = {
    "Pending": "#94A3B8",
    "Processing": "#22D3EE",
    "Completed": "#34D399",
    "Failed": "#FB7185",
    "Reading": "#22D3EE",
    "Read": "#34D399",
    "No text": "#FBBF24",
}
OCR_ROW_FIELDS = (
    "ocr_text",
    "ocr_status",
    "ocr_error",
    "suggested_negeri",
    "suggested_dun_code",
    "suggested_dun_name",
    "match_status",
    "match_reason",
    "confirmed_negeri",
    "confirmed_dun_code",
    "confirmed_dun_name",
    "mark_status",
    "mark_confidence",
    "mark_reason",
    "mark_row_text",
    "mark_diagnosis",
)


def _store_late_reading(store, path: str, payload) -> None:
    """Keep a finished reading after the import dialog has closed. Do not clear a confirmation."""
    reading, marks = payload
    fields = fields_from_inspection(reading, marks, source_path=path)
    for key in ("confirmed_negeri", "confirmed_dun_code", "confirmed_dun_name"):
        fields.pop(key, None)
    store.update_ballot_reading(Path(path).name, fields, source_path=path)


def _thread_running(worker: QThread | None) -> bool:
    if worker is None:
        return False
    try:
        return worker.isRunning()
    except RuntimeError:
        return False


def _blank_row(path: str) -> dict:
    row = {
        "path": str(Path(path)),
        "name": Path(path).name,
        "status": "Pending",
        "detail": "Waiting to process.",
    }
    row.update({field: "" for field in OCR_ROW_FIELDS})
    return row


class ImportBallotDialog(QDialog):
    inspection_ready = Signal(object)

    def __init__(self, store, image_path: str, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self.image_path = image_path
        self._progress = 0
        self._outcome = "idle"
        self._closed = False
        self.ocr_worker = None
        self.inspection_fields = None
        self._shutdown_hook = self._pause_for_shutdown
        register_shutdown_hook(self._shutdown_hook)
        self.destroyed.connect(self._drop_shutdown_hook)
        self.setWindowTitle("Imported Ballot Image")
        self.setModal(True)
        self.setMinimumSize(760, 680)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(
            SectionTitle(
                "Imported Ballot Image",
                "Location and candidate marks are read from this image. A vote is recorded only when both checks pass.",
            )
        )
        layout.addWidget(
            NoticeBar(
                "A provisional vote is recorded only for one clear mark on a candidate registered for the detected DUN. Unclear ballots go to the review queue.",
                "info",
            )
        )

        self.preview = QLabel()
        self.preview.setObjectName("previewFrame")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(160)
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
        self.ocr_panel = OcrDetailPanel()
        layout.addWidget(self.ocr_panel)
        if self._readable:
            self._start_ocr()

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
        self.review_btn = QPushButton("Open in review queue")
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
                "Cannot process. Demo Processing Mode is off, so this image was not added to the review queue."
            )
            self._outcome = "failed"
            self.process_btn.setEnabled(False)
            return
        self.store.add_imported([self.image_path])
        self._progress = 0
        self.progress.setValue(0)
        self.process_btn.setEnabled(False)
        self.status.setText("Adding this image to the officer review queue.")
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
                "Added to the officer review queue. No vote was counted."
            )
            result = self.store.complete_import_processing(
                1,
                source_paths=[self.image_path],
                reading=self.ocr_panel.snapshot(),
            )
            if result == "counted":
                self.status.setText(COUNTED_RESULT)
            elif result == "duplicate":
                self.status.setText("This image was already counted. No additional vote was recorded.")
            else:
                self.status.setText(QUEUED_RESULT)
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

    def _pause_for_shutdown(self) -> None:
        self._closed = True
        if self.timer.isActive():
            self.timer.stop()

    def _drop_shutdown_hook(self, *_args) -> None:
        unregister_shutdown_hook(self._shutdown_hook)

    def _start_ocr(self) -> None:
        self.ocr_panel.load(self.image_path, {"ocr_status": "Reading", "match_reason": "Reading text…"})
        self.ocr_worker = InspectWorker(self.image_path, None)
        retain_until_finished(self.ocr_worker)
        self.ocr_worker.completed.connect(self._on_ocr, Qt.ConnectionType.QueuedConnection)
        self.ocr_worker.start()

    def _on_ocr(self, payload) -> None:
        if is_shutting_down():
            return
        reading, marks = payload
        fields = fields_from_inspection(reading, marks, source_path=self.image_path)
        self.inspection_fields = fields
        if not self._closed:
            self.ocr_panel.load(self.image_path, fields)
            if self._outcome == "completed":
                self.store.update_ballot_reading(
                    Path(self.image_path).name,
                    fields,
                    source_path=self.image_path,
                )
        elif self._outcome == "completed":
            _store_late_reading(self.store, self.image_path, payload)
        self.inspection_ready.emit(fields)

    def closeEvent(self, event) -> None:  # noqa: N802
        self._closed = True
        if self.timer.isActive():
            self.timer.stop()
        super().closeEvent(event)


class ScanPage(QWidget):
    navigate = Signal(str)

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self.store = store
        self._batch_rows: list[dict] = []
        self._batch_index = 0
        self._batch_running = False
        self._batch_token = 0
        self._batch_timer = QTimer(self)
        self._batch_timer.setSingleShot(True)
        self._batch_timer.timeout.connect(self._process_next_batch_row)
        self._shutdown_hook = self._pause_for_shutdown
        register_shutdown_hook(self._shutdown_hook)
        self.destroyed.connect(self._drop_shutdown_hook)
        self._held_dialog = None
        self._awaiting_inspection_path = None
        self.setObjectName("pageBody")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 12, 24, 16)
        root.setSpacing(10)
        root.addWidget(
            NoticeBar(
                "Negeri and DUN are detected from each image. A vote is counted only when that location is reliable and exactly one clear mark matches the official candidate for that DUN.",
                "info",
            )
        )
        workspace = QHBoxLayout()
        workspace.setSpacing(12)
        workspace.setAlignment(Qt.AlignmentFlag.AlignTop)
        import_card = self._build_import_card()
        import_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        workspace.addWidget(import_card, 2, Qt.AlignmentFlag.AlignTop)
        workspace.addWidget(self._build_preview_card(), 3)
        root.addLayout(workspace, 1)
        root.addWidget(self._build_camera_card())

    def _build_import_card(self) -> Card:
        card = Card()
        card.layout.addWidget(
            SectionTitle(
                "Import ballot images",
                "Upload Image accepts one or more files. Upload Folder imports the images in a folder.",
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
        upload_row = QHBoxLayout()
        upload_row.setSpacing(8)
        upload_image = QPushButton("Upload Image")
        upload_image.setObjectName("primaryButton")
        upload_image.clicked.connect(self._choose_files)
        upload_folder = QPushButton("Upload Folder")
        upload_folder.clicked.connect(self._choose_folder)
        upload_row.addWidget(upload_image)
        upload_row.addWidget(upload_folder)
        upload_row.addStretch(1)
        self._import_buttons = (upload_image, upload_folder)
        card.layout.addLayout(upload_row)
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
        self.batch_table = QTableWidget(0, 4)
        self.batch_table.setObjectName("batchTable")
        self.batch_table.setHorizontalHeaderLabels(["Filename", "Status", "OCR", "Result"])
        style_data_table(self.batch_table)
        header = self.batch_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.batch_table.setMinimumHeight(132)
        self.batch_table.setMaximumHeight(220)
        self.batch_table.itemSelectionChanged.connect(self._on_batch_select)
        self.batch_table.setVisible(False)
        card.layout.addWidget(self.batch_table)
        self.page_preview = QLabel("No image selected")
        self.page_preview.setObjectName("previewFrame")
        self.page_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_preview.setWordWrap(True)
        self.page_preview.setMinimumHeight(120)
        self.page_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.layout.addWidget(self.page_preview, 1)
        details_caption = QLabel("File details")
        details_caption.setObjectName("fieldCaption")
        card.layout.addWidget(details_caption)
        self.preview_notes = QLabel(
            "No file is open. Use Upload Image for one or more files, or Upload Folder for a directory."
        )
        self.preview_notes.setObjectName("mutedLabel")
        self.preview_notes.setWordWrap(True)
        card.layout.addWidget(self.preview_notes)
        self.ocr_panel = OcrDetailPanel()
        card.layout.addWidget(self.ocr_panel)
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
            "completed": "Added to the officer review queue. No vote was counted.",
            "cancelled": "Import cancelled. No ballot was classified.",
            "failed": "The file was not processed.",
            "review": "Queued for officer review.",
            "idle": "Dialog closed before processing.",
        }.get(outcome, "File selected.")
        self.preview_notes.setText(f"{name}\n{dims}\n\n{outcome_text}")

    def _choose_files(self) -> None:
        if self._batch_running:
            return
        paths, _filter = QFileDialog.getOpenFileNames(self, "Import ballot images", "", IMAGE_FILTER)
        if not paths:
            return
        if len(paths) == 1:
            self._open_single(paths[0])
            return
        self.start_batch(paths)

    def _open_single(self, path: str) -> None:
        if Path(path).suffix.lower() not in ALLOWED:
            QMessageBox.warning(self, "Unsupported file", "Use PNG, JPG, or JPEG.")
            return
        if self.store.data.get("imported"):
            self.store.clear_imported()
        dialog = ImportBallotDialog(self.store, path, self)
        self._awaiting_inspection_path = path
        dialog.inspection_ready.connect(self._show_finished_inspection)
        result = dialog.exec()
        self.last_import.setText(f"Last file: {Path(path).name}")
        self._show_file_preview(path, dialog._outcome)
        if dialog.inspection_fields is not None:
            self.ocr_panel.load(path, dialog.inspection_fields)
            self._held_dialog = None
        elif _thread_running(dialog.ocr_worker):
            self._held_dialog = dialog
        else:
            self._held_dialog = None
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

    def _show_finished_inspection(self, fields: dict) -> None:
        path = str(fields.get("source_path") or "")
        if self._awaiting_inspection_path not in {None, path}:
            return
        if path:
            self.ocr_panel.load(path, fields)
            self._awaiting_inspection_path = None
            self._held_dialog = None

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
            self._batch_rows = [_blank_row(path) for path in unique]
        self._batch_index = 0
        self._batch_token += 1
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
        problem = self._image_problem(row["path"])
        if problem is not None:
            row["status"] = "Failed"
            row["detail"] = problem
            row["ocr_status"] = "Failed" if "image" in problem.casefold() or "format" in problem.casefold() else ""
            self._batch_index += 1
            self._render_batch(select=self._batch_index - 1)
            self._batch_timer.start(0)
            return
        row["status"] = "Processing"
        row["ocr_status"] = "Reading"
        row["detail"] = "Reading text, then queueing this image."
        self._render_batch(select=self._batch_index)
        token = self._batch_token
        worker = InspectWorker(row["path"], None)
        retain_until_finished(worker)
        worker.completed.connect(
            lambda payload, path=row["path"], token=token: self._finish_row_ocr(
                path, token, payload
            ),
            Qt.ConnectionType.QueuedConnection,
        )
        worker.start()

    def _pause_for_shutdown(self) -> None:
        self._batch_token += 1
        self._batch_running = False
        self._batch_timer.stop()

    def _drop_shutdown_hook(self, *_args) -> None:
        unregister_shutdown_hook(self._shutdown_hook)

    def _finish_row_ocr(self, path: str, token: int, payload) -> None:
        if is_shutting_down() or token != self._batch_token or not self._batch_running:
            return
        reading, marks = payload
        row = next((item for item in self._batch_rows if item["path"] == path and item["status"] == "Processing"), None)
        if row is None:
            return
        fields = self.ocr_panel.apply_inspection(path, reading, marks) if self.ocr_panel.path == path else None
        stored = fields_from_inspection(reading, marks, source_path=path)
        confirmed = {
            "confirmed_negeri": row.get("confirmed_negeri", ""),
            "confirmed_dun_code": row.get("confirmed_dun_code", ""),
            "confirmed_dun_name": row.get("confirmed_dun_name", ""),
        }
        if fields is not None and fields.get("confirmed_negeri"):
            confirmed = {
                "confirmed_negeri": fields.get("confirmed_negeri", ""),
                "confirmed_dun_code": fields.get("confirmed_dun_code", ""),
                "confirmed_dun_name": fields.get("confirmed_dun_name", ""),
            }
        stored.update(confirmed)
        row.update(stored)
        status, detail = self._process_image(path, stored)
        row["status"] = status
        row["detail"] = detail
        self._batch_index += 1
        self._render_batch(select=self.batch_table.currentRow() if self.batch_table.currentRow() >= 0 else self._batch_index - 1)
        if self._batch_running:
            self._batch_timer.start(0)

    def _image_problem(self, path: str) -> str | None:
        file_path = Path(path)
        if file_path.suffix.lower() not in ALLOWED:
            return "Unsupported format. Use PNG, JPG, or JPEG."
        if not file_path.is_file():
            return "File could not be found."
        if QPixmap(str(file_path)).isNull():
            return "This file could not be opened as an image."
        if not self.store.settings().get("demo_processing_mode", True):
            return "Cannot process. Demo Processing Mode is off, so this image was not added to the review queue."
        return None

    def _process_image(self, path: str, reading_fields: dict | None = None) -> tuple[str, str]:
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
                "Cannot process. Demo Processing Mode is off, so this image was not added to the review queue.",
            )
        before = int(self.store.data["stats"].get("pending_reviews", 0))
        try:
            self.store.add_imported([str(file_path)], notify=False)
            result = self.store.complete_import_processing(
                1,
                source_paths=[str(file_path)],
                notify=False,
                reading=reading_fields,
            )
        except Exception as exc:
            return "Failed", f"Processing error: {exc}"
        after = int(self.store.data["stats"].get("pending_reviews", 0))
        if result == "counted":
            return "Completed", COUNTED_RESULT
        if result == "duplicate":
            return "Completed", "This image was already counted. No additional vote was recorded."
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
                for field in OCR_ROW_FIELDS:
                    row[field] = ""
        self.start_batch([], retry=True)

    def _cancel_batch(self) -> None:
        if not self._batch_running:
            return
        self._batch_token += 1
        self._batch_running = False
        self._batch_timer.stop()
        for row in self._batch_rows:
            if row["status"] == "Processing":
                row["status"] = "Pending"
                row["ocr_status"] = ""
                row["detail"] = "Waiting to process."
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
            ocr_item = aligned_item(row.get("ocr_status") or "—")
            ocr_item.setForeground(QColor(STATUS_COLOR.get(row.get("ocr_status", ""), "#94A3B8")))
            ocr_item.setToolTip(row.get("ocr_error") or row.get("match_reason") or "")
            detail_item = aligned_item(row["detail"])
            detail_item.setToolTip(row["detail"])
            self.batch_table.setItem(index, 0, name_item)
            self.batch_table.setItem(index, 1, status_item)
            self.batch_table.setItem(index, 2, ocr_item)
            self.batch_table.setItem(index, 3, detail_item)
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
        if self.ocr_panel.path != row["path"]:
            self.ocr_panel.load(row["path"], row)

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
        self.store.message.emit("Camera is not connected. Use Upload Image or Upload Folder instead.", "warning")
