"""Bulk import checks: one file, many files, a folder, and mixed failures."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.core.store import Store
from app.pages.scan_page import QUEUED_RESULT, ImportBallotDialog, ScanPage, files_in_folder
from main import load_stylesheet


def _save_png(folder: Path, name: str) -> Path:
    image = QImage(80, 48, QImage.Format.Format_RGB32)
    image.fill(0x1B2940)
    path = folder / name
    assert image.save(str(path))
    return path


def _save_jpg(folder: Path, name: str) -> Path:
    image = QImage(64, 40, QImage.Format.Format_RGB32)
    image.fill(0x334155)
    path = folder / name
    assert image.save(str(path), "JPG")
    return path


def _drain(app: QApplication, page: ScanPage) -> None:
    for _ in range(500):
        app.processEvents()
        if not page._batch_running and not page._batch_timer.isActive():
            return
    raise AssertionError("batch did not finish")


def _queued_names(store: Store) -> list[str]:
    return [item.get("source_file", "") for item in store.data["flagged"] if item.get("source_file")]


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())
    store = Store()
    page = ScanPage(store)
    baseline = store.data["stats"]["pending_reviews"]

    with tempfile.TemporaryDirectory() as folder_name:
        folder = Path(folder_name)
        one = _save_png(folder, "one.png")
        dialog = ImportBallotDialog(store, str(one))
        dialog._start()
        dialog._progress = 98
        dialog._tick()
        dialog._tick()
        assert dialog._outcome == "completed"
        assert store.data["stats"]["pending_reviews"] == baseline + 1
        assert _queued_names(store)[0] == "one.png"

        first = _save_png(folder, "alpha.png")
        second = _save_jpg(folder, "beta.jpg")
        page.start_batch([str(first), str(second), str(first)])
        _drain(app, page)
        assert [row["status"] for row in page._batch_rows] == ["Completed", "Completed"]
        assert all(row["detail"] == QUEUED_RESULT for row in page._batch_rows)
        assert store.data["stats"]["pending_reviews"] == baseline + 3
        assert _queued_names(store)[:2] == ["beta.jpg", "alpha.png"]
        assert "2 images · 2 completed · 0 failed" in page.batch_summary.text()

        mixed = folder / "mixed"
        mixed.mkdir()
        good = _save_png(mixed, "good.png")
        bad_type = mixed / "notes.txt"
        bad_type.write_text("not a ballot", encoding="utf-8")
        corrupt = mixed / "broken.png"
        corrupt.write_bytes(b"this is not a png")
        _save_jpg(mixed, "also-good.jpg")
        before_mixed = store.data["stats"]["pending_reviews"]
        page.start_batch(files_in_folder(str(mixed)))
        _drain(app, page)
        by_name = {row["name"]: row for row in page._batch_rows}
        assert by_name["also-good.jpg"]["status"] == "Completed"
        assert by_name["good.png"]["status"] == "Completed"
        assert by_name["notes.txt"]["status"] == "Failed"
        assert "Unsupported format" in by_name["notes.txt"]["detail"]
        assert by_name["broken.png"]["status"] == "Failed"
        assert "could not be opened" in by_name["broken.png"]["detail"]
        assert store.data["stats"]["pending_reviews"] == before_mixed + 2
        assert "4 images · 2 completed · 2 failed" in page.batch_summary.text()

        assert [Path(path).name for path in files_in_folder(str(mixed))] == [
            "also-good.jpg",
            "broken.png",
            "good.png",
            "notes.txt",
        ]

        store.settings()["demo_processing_mode"] = False
        held = store.data["stats"]["pending_reviews"]
        retry_names = {row["name"] for row in page._batch_rows if row["status"] == "Failed"}
        page._retry_failed()
        _drain(app, page)
        assert {row["name"] for row in page._batch_rows if row["status"] == "Failed"} >= retry_names
        assert by_name["good.png"]["status"] == "Completed"
        assert store.data["stats"]["pending_reviews"] == held

        store.settings()["demo_processing_mode"] = True
        corrupt.write_bytes(good.read_bytes())
        page._retry_failed()
        _drain(app, page)
        by_name = {row["name"]: row for row in page._batch_rows}
        assert by_name["broken.png"]["status"] == "Completed"
        assert by_name["broken.png"]["detail"] == QUEUED_RESULT
        assert by_name["notes.txt"]["status"] == "Failed"
        assert by_name["good.png"]["status"] == "Completed"
        assert store.data["stats"]["pending_reviews"] == held + 1
        queued = _queued_names(store)
        assert queued.count("broken.png") == 1
        assert queued.count("good.png") == 1

    print("batch import ok")


if __name__ == "__main__":
    main()
