"""Scan Ballots OCR: per-image text, suggestions, correction, and an unchanged review queue."""

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.core.constants import USER_NAME
from app.core.store import REASON_AWAITING, REASON_LOCATION, REASON_OCR_FAILED, Store, reason_for_reading
from app.services.candidate_match import MISMATCH_REASON
from app.pages.review_page import DECISIONS, ReviewPage
from app.pages.scan_page import ImportBallotDialog, ScanPage
from app.services.location_match import HIGH, LOW, NOT_DETECTED, LocationMatch
from app.services.ocr_service import BallotReading, OcrResult
from app.widgets.ocr_panel import fields_from_reading
from main import load_stylesheet

_ARIAL = Path(r"C:\Windows\Fonts\arial.ttf")


def _font() -> str:
    if not _ARIAL.is_file():
        raise AssertionError(f"OCR test setup error: Arial was not found at {_ARIAL}.")
    font_id = QFontDatabase.addApplicationFont(str(_ARIAL))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
    if not families:
        raise AssertionError(f"OCR test setup error: Qt could not load {_ARIAL}.")
    return families[0]


def _paint(path: Path, lines: list[str]) -> None:
    image = QImage(900, 280, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont(_font(), 36))
    for index, line in enumerate(lines):
        painter.drawText(40, 80 + index * 80, line)
    painter.end()
    assert image.save(str(path))


def _blank(path: Path) -> None:
    image = QImage(80, 48, QImage.Format.Format_RGB32)
    image.fill(0x1B2940)
    assert image.save(str(path))


def _wait(app: QApplication, ready, timeout: float = 45) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if ready():
            return
        time.sleep(0.02)
    raise AssertionError("timed out waiting for OCR")


def _votes(store: Store) -> dict:
    return {item.get("candidate_name"): item.get("vote_count") for item in store.data["candidates"]}


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())
    store = Store()
    page = ScanPage(store)
    election_before = (
        store.data["election"]["negeri"],
        store.data["election"].get("dun_code"),
        store.data["election"].get("dun"),
    )
    votes_before = _votes(store)
    assert ("Confirm Detected Mark", "Confirm mark") in DECISIONS
    assert ("Mark as Rejected", "Reject ballot") in DECISIONS
    assert ("Send for Further Review", "Send for further review") in DECISIONS

    empty = fields_from_reading(
        BallotReading(
            ocr=OcrResult(True, "   ", ("eng", "msa"), None, "", "", 0),
            location=LocationMatch(None, None, None, None, NOT_DETECTED, NOT_DETECTED, NOT_DETECTED, "ignored"),
        )
    )
    assert empty["ocr_status"] == "No text"
    assert empty["ocr_text"] == ""
    assert empty["suggested_negeri"] == ""
    failed = fields_from_reading(
        BallotReading(
            ocr=OcrResult(False, "invented", ("eng", "msa"), None, "Tesseract is missing.", "missing_executable", 0),
            location=LocationMatch("Johor", "JHR", "N.01", "Buloh Kasap", "High confidence", "High confidence", "High confidence", "no"),
        )
    )
    assert failed["ocr_status"] == "Failed"
    assert failed["ocr_text"] == ""
    assert failed["suggested_negeri"] == ""
    uncertain = fields_from_reading(
        BallotReading(
            ocr=OcrResult(True, "N.01", ("eng", "msa"), None, "", "", 0),
            location=LocationMatch("Johor", "JHR", "N.01", "Buloh Kasap", LOW, HIGH, LOW, "Negeri only"),
        )
    )
    assert uncertain["match_status"] == LOW
    assert uncertain["suggested_negeri"] == ""
    assert uncertain["suggested_dun_code"] == ""
    reliable = fields_from_reading(
        BallotReading(
            ocr=OcrResult(True, "Johor\nN.01 Buloh Kasap\nAli bin Abu", ("eng", "msa"), None, "", "", 0),
            location=LocationMatch("Johor", "JHR", "N.01", "Buloh Kasap", HIGH, HIGH, HIGH, "Matched"),
        )
    )
    assert reliable["ocr_text"].count("\n") == 2
    assert "Ali bin Abu" in reliable["ocr_text"]
    assert reliable["suggested_negeri"] == "Johor"
    assert reason_for_reading(reliable) == REASON_AWAITING
    assert reason_for_reading(failed) == REASON_OCR_FAILED
    assert reason_for_reading(uncertain) == REASON_LOCATION
    assert reason_for_reading(empty) == REASON_LOCATION

    with tempfile.TemporaryDirectory() as folder_name:
        folder = Path(folder_name)
        johor = folder / "johor-ballot.png"
        kedah = folder / "kedah-ballot.png"
        blank = folder / "blank.png"
        notes = folder / "notes.txt"
        _paint(johor, ["Johor", "N.01 Buloh Kasap", "Ali bin Abu"])
        _paint(kedah, ["Kedah", "N.01 Ayer Hangat", "Siti binti Ahmad"])
        ambiguous = folder / "code-only.png"
        _paint(ambiguous, ["N.01"])
        _blank(blank)
        notes.write_text("not a ballot", encoding="utf-8")

        early = ImportBallotDialog(store, str(johor))
        early.close()
        assert early.ocr_worker is not None
        _wait(app, lambda: not early.ocr_worker.isRunning())

        button_labels = [button.text() for button in page.findChildren(QPushButton)]
        assert button_labels.count("Upload Image") == 1
        assert button_labels.count("Upload Folder") == 1
        assert "Import Ballot Image" not in button_labels
        assert "Import images" not in button_labels
        assert "Import folder" not in button_labels

        dialog = ImportBallotDialog(store, str(johor))
        _wait(app, lambda: dialog.ocr_panel.snapshot().get("ocr_status") in {"Read", "No text", "Failed"} and dialog.ocr_panel.snapshot().get("mark_status"))
        shown = dialog.ocr_panel.snapshot().get("ocr_text") or ""
        assert "Johor" in shown, shown
        assert "Buloh Kasap" in shown, shown
        assert "Ali bin Abu" in shown, shown
        assert dialog.findChild(QLabel, "ocrText") is None
        assert all(label.text() != "Extracted text" for label in dialog.findChildren(QLabel))
        assert dialog.ocr_panel.detected_negeri.text() == "Johor"
        assert "Buloh Kasap" in dialog.ocr_panel.detected_dun.text()
        assert dialog.ocr_panel.detected_candidate.text() == "Not Detected"
        assert "No candidate mark detected" in dialog.ocr_panel.detection_reason.text()
        assert dialog.ocr_panel.match_badge.text() == "High Confidence"
        assert dialog.process_btn.isEnabled()
        assert "Ready" in dialog.status.text()
        notice = dialog.findChild(QLabel, "noticeText")
        assert notice is not None and "review queue" in notice.text().casefold()
        dialog._start()
        dialog._progress = 98
        dialog._tick()
        dialog._tick()
        assert dialog._outcome == "completed"
        ballot = store.data["flagged"][0]
        assert ballot["source_file"] == "johor-ballot.png"
        assert ballot["source_path"] == str(johor)
        assert "Johor" in ballot["ocr_text"]
        assert "Ali bin Abu" in ballot["ocr_text"]
        assert ballot["ocr_text"] == shown.strip()
        assert ballot["suggested_negeri"] == "Johor"
        assert ballot["suggested_dun_code"] == "N.01"
        assert ballot["detected"] == ""
        assert ballot["reason"] == "No candidate mark detected."
        assert ballot["counted"] is False
        assert (store.data["election"]["negeri"], store.data["election"].get("dun_code"), store.data["election"].get("dun")) == election_before

        review = ReviewPage(store)
        review.selected_id = ballot["id"]
        review.refresh()
        assert review.meta_id.text() == ballot["id"]
        assert review.review_negeri.text() == "Johor"
        assert "Buloh Kasap" in review.review_dun.text()
        assert review.confidence.text() == "High Confidence"
        assert review.status_badge.text() == "Pending Review"
        assert review.meta_reason.text() == "No candidate mark detected."
        assert review.mark_confidence.text() in {"Not Detected", "Low Confidence", "High Confidence"}
        assert not review.imported_preview.isHidden()
        assert review.preview.isHidden()
        assert review.imported_preview.toolTip() == str(johor)
        assert not review.imported_preview.pixmap().isNull()
        assert "could not be opened" not in review.imported_preview.text()

        page.start_batch([str(johor), str(kedah)])
        _wait(app, lambda: any(row["status"] == "Processing" for row in page._batch_rows))
        page.batch_table.selectRow(1)
        app.processEvents()
        _wait(app, lambda: page._batch_rows[0]["status"] == "Completed")
        assert page.ocr_panel.path == str(kedah)
        assert "Buloh Kasap" not in page.ocr_panel.detected_dun.text()
        _wait(app, lambda: not page._batch_running and not page._batch_timer.isActive())
        by_name = {row["name"]: row for row in page._batch_rows}
        assert "Johor" in by_name["johor-ballot.png"]["ocr_text"]
        assert by_name["johor-ballot.png"]["suggested_dun_name"] == "Buloh Kasap"
        assert "Kedah" in by_name["kedah-ballot.png"]["ocr_text"]
        assert by_name["kedah-ballot.png"]["suggested_dun_name"] == "Ayer Hangat"
        assert by_name["johor-ballot.png"]["ocr_text"] != by_name["kedah-ballot.png"]["ocr_text"]
        page.batch_table.selectRow(0)
        app.processEvents()
        assert "Buloh Kasap" in page.ocr_panel.detected_dun.text()
        assert "Johor" in (page.ocr_panel.snapshot().get("ocr_text") or "")
        page.batch_table.selectRow(1)
        app.processEvents()
        assert "Ayer Hangat" in page.ocr_panel.detected_dun.text()
        assert "Siti binti Ahmad" in (page.ocr_panel.snapshot().get("ocr_text") or "")
        assert page.ocr_panel.detected_candidate.text() == "Not Detected"
        assert page.ocr_panel.detected_negeri.text() == "Kedah"
        assert "Ayer Hangat" in page.ocr_panel.detected_dun.text()
        kedah_ballot = next(item for item in store.data["flagged"] if item.get("source_path") == str(kedah))
        review.selected_id = kedah_ballot["id"]
        review.refresh()
        assert review.imported_preview.toolTip() == str(kedah)
        assert review.imported_preview.toolTip() != str(johor)
        review.selected_id = ballot["id"]
        review.refresh()
        assert review.imported_preview.toolTip() == str(johor)
        missing = dict(ballot)
        missing["source_path"] = str(folder / "missing-ballot.png")
        review._show_ballot_image(missing)
        assert "could not be opened" in review.imported_preview.text()
        review._show_ballot_image({"id": "BLT-DEMO"})
        assert not review.preview.isHidden()
        assert review.imported_preview.isHidden()

        low = ImportBallotDialog(store, str(ambiguous))
        _wait(app, lambda: low.ocr_panel.snapshot().get("ocr_status") in {"Read", "No text", "Failed"})
        assert low.ocr_panel.snapshot().get("suggested_negeri", "") == ""
        assert low.ocr_panel.snapshot().get("suggested_dun_code", "") == ""
        assert low.ocr_panel.detected_negeri.text() == "Not Detected"
        assert low.ocr_panel.detected_dun.text() == "Not Detected"
        assert low.ocr_panel.detected_candidate.text() == "Not Detected"
        assert low.ocr_panel.detection_reason.text() == "Location could not be verified."
        assert low.ocr_panel.match_badge.text() in {"Low Confidence", "Not Detected"}
        assert reason_for_reading(low.ocr_panel.snapshot()) == REASON_LOCATION
        assert (store.data["election"]["negeri"], store.data["election"].get("dun_code")) == election_before[:2]

        page.start_batch([str(blank), str(notes), str(kedah)])
        _wait(app, lambda: not page._batch_running and not page._batch_timer.isActive(), timeout=60)
        mixed = {row["name"]: row for row in page._batch_rows}
        assert mixed["blank.png"]["status"] == "Completed"
        assert mixed["blank.png"]["ocr_status"] != "Read" or mixed["blank.png"]["ocr_text"].strip()
        assert not (mixed["blank.png"]["ocr_status"] == "Read" and not mixed["blank.png"]["ocr_text"].strip())
        assert mixed["notes.txt"]["status"] == "Failed"
        assert mixed["kedah-ballot.png"]["status"] == "Completed"
        assert mixed["kedah-ballot.png"]["suggested_negeri"] == "Kedah"
        queued = [item for item in store.data["flagged"] if item.get("source_file") == "blank.png"]
        assert queued
        assert queued[0]["detected"] == ""
        assert queued[0]["status"] == "Pending Review"

        target = next(item for item in store.data["flagged"] if item.get("source_file") == "kedah-ballot.png")
        store.submit_review(target["id"], "Confirm Detected Mark", "no mark on the image")
        assert target["status"] == "Reviewed"
        assert target["decision"] == "Confirm Detected Mark"
        assert target["detected"] == ""
        record = target["review_record"]
        assert record["ballot_id"] == target["id"]
        assert record["image_ref"] == str(kedah)
        assert record["decision"] == "Confirm Detected Mark"
        assert record["review_reason"] == target["reason"]
        assert record["officer"] == USER_NAME
        assert record["timestamp"]
        fresh = Store()
        assert target["id"] not in {item["id"] for item in fresh.data["flagged"]}
        assert _votes(store) == votes_before
        other = next(item for item in store.data["flagged"] if item.get("source_file") == "blank.png")
        store.submit_review(other["id"], "Mark as Rejected", "unreadable")
        assert other["decision"] == "Mark as Rejected"
        assert other["detected"] == ""
        third = next(item for item in store.data["flagged"] if item.get("source_file") == "johor-ballot.png" and item["status"] == "Pending Review")
        third["detected"] = "Ghost Person"
        votes_with_unknown = _votes(store)
        store.submit_review(third["id"], "Send for Further Review", "check the location")
        assert third["decision"] == "Send for Further Review"
        assert third["detected"] == "Ghost Person"
        assert third["candidate_mismatch"] is True
        assert "not in the registered candidate list" in third["mismatch_reason"]
        assert _votes(store) == votes_with_unknown
        listed = next(item for item in store.data["flagged"] if item["status"] == "Pending Review")
        before_names = _votes(store)
        assert store.record_observed_candidates(listed["id"], ["Amalia"])
        assert listed["candidate_mismatch"] is True
        assert listed["detected"] == ""
        assert listed["unknown_candidates"] == ["Amalia"]
        assert listed["mismatch_reason"] == MISMATCH_REASON
        assert _votes(store) == before_names
        assert listed["detected"] == ""
        assert "Amalia Suria" not in listed.get("unknown_candidates", [])
        assert third["decision"] == "Send for Further Review"
        assert third["detected"] == "Ghost Person"
        assert _votes(store) == votes_before
        assert (store.data["election"]["negeri"], store.data["election"].get("dun_code"), store.data["election"].get("dun")) == election_before

        from app.services.thread_cleanup import shutdown_background_workers

        closing = ImportBallotDialog(store, str(johor))
        closing.close()
        shutdown_background_workers()
        assert closing.ocr_worker is not None
        assert not closing.ocr_worker.isRunning()

    print("scan ocr checks ok")


if __name__ == "__main__":
    main()
