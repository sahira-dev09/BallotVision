"""Headless UI smoke test at 1440x900."""

import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from app.core.candidates import DEMO_CANDIDATES, DEMO_VOTE_COUNTS
from app.core.constants import APP_BRAND_TAG, APP_NAME
from app.core.store import Store
from app.main_window import MainWindow
from app.pages.scan_page import ImportBallotDialog
from app.widgets.avatar import officer_avatar_pixmap
from app.widgets.logo import logo_icon
from app.widgets.portraits import candidate_portrait_pixmap
from main import load_stylesheet


def _candidate_totals(store: Store) -> dict[str, int]:
    return {item["candidate_id"]: int(item["vote_count"]) for item in store.data["candidates"]}


def _named_candidates(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel) if label.objectName() == "candidateName"]


def main() -> None:
    app = QApplication(sys.argv)
    app.setWindowIcon(logo_icon(256))
    app.setStyleSheet(load_stylesheet())
    photo = officer_avatar_pixmap(40)
    assert not photo.isNull()
    icon = logo_icon(256)
    assert not icon.isNull()
    store = Store()
    win = MainWindow(store)
    win.closeEvent = lambda event: event.accept()
    win.resize(1440, 900)
    win.show()
    app.processEvents()

    assert APP_BRAND_TAG in win.windowTitle()
    assert APP_NAME in win.windowTitle()
    assert "FYP Desktop Prototype" not in win.windowTitle()
    assert not win.windowIcon().isNull()
    header = win.demo_chip.parentWidget().parentWidget()
    chip_bottom = win.demo_chip.mapTo(header, win.demo_chip.rect().bottomRight()).y()
    info_bottom = win.info_button.mapTo(header, win.info_button.rect().bottomRight()).y()
    profile_bottom = win.profile_button.mapTo(header, win.profile_button.rect().bottomRight()).y()
    assert chip_bottom <= header.height(), (chip_bottom, header.height())
    assert info_bottom <= header.height(), (info_bottom, header.height())
    assert profile_bottom <= header.height(), (profile_bottom, header.height())
    assert 36 <= win.demo_chip.height() <= 44
    assert 36 <= win.info_button.height() <= 44
    assert win.profile_button.height() <= 48
    negeri = win.pages["dashboard"].location.negeri
    dun = win.pages["dashboard"].location.dun
    assert negeri.objectName() == "locationCombo"
    assert dun.objectName() == "locationCombo"
    assert negeri.count() > 1
    assert dun.count() > 1
    win.resize(1180, 760)
    app.processEvents()
    chip_bottom = win.demo_chip.mapTo(header, win.demo_chip.rect().bottomRight()).y()
    assert chip_bottom <= header.height()
    win.resize(1440, 900)
    app.processEvents()

    assert store.data["election"]["dun_code"] == "N.01"
    assert store.data["stats"]["total_processed"] == 2450
    names = {item["candidate_name"] for item in store.data["candidates"]}
    assert names == {item["candidate_name"] for item in DEMO_CANDIDATES}
    assert "Candidate A" not in names
    johor_votes = _candidate_totals(store)
    assert johor_votes == DEMO_VOTE_COUNTS
    assert sum(johor_votes.values()) == store.data["stats"]["valid"]
    stats = store.data["stats"]
    assert stats["valid"] + stats["rejected"] + stats["pending_reviews"] == stats["total_processed"]
    assert all(item["result_status"] == "none" for item in store.data["candidates"])
    pixmaps = []
    for item in DEMO_CANDIDATES:
        pixmap = candidate_portrait_pixmap(item, 48)
        assert not pixmap.isNull()
        pixmaps.append(pixmap.toImage().pixel(24, 24))
    assert len(set(pixmaps)) == 4

    dash_names = _named_candidates(win.pages["dashboard"].candidate_list)
    result_names = _named_candidates(win.pages["results"].candidate_list)
    assert dash_names == result_names[:3]
    assert set(result_names) == names
    expected_order = [
        "Amalia Suria",
        "Rizal Purnama",
        "Nora Bentara",
        "Faizal Ombak",
    ]
    assert result_names == expected_order
    votes = [int(item["vote_count"]) for item in store.data["candidates"]]
    displayed = result_names
    assert displayed == expected_order

    store.set_demo_location("Kedah", "N.01", "Ayer Hangat")
    app.processEvents()
    assert store.data["election"]["data_kind"] == "none"
    assert store.data["stats"]["total_processed"] == 0
    assert sum(_candidate_totals(store).values()) == 0
    assert not win.pages["results"].content.isVisible()

    store.set_demo_location("W.P. Putrajaya", "", "")
    assert store.data["election"]["data_kind"] == "not_applicable"
    assert store.data["election"]["dun_code"] == ""

    store.set_demo_location("Johor", "N.01", "Buloh Kasap")
    app.processEvents()
    assert store.data["stats"]["total_processed"] == 2450
    assert _candidate_totals(store) == johor_votes
    assert {item["candidate_name"] for item in store.data["candidates"]} == names

    image = QImage(320, 180, QImage.Format.Format_RGB32)
    image.fill(0x1B2940)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "sample_ballot.png"
        image.save(str(path))
        dialog = ImportBallotDialog(store, str(path), win)
        assert dialog.process_btn.isEnabled()
        assert not dialog.timer.isActive()
        assert "Ready" in dialog.status.text()
        dialog._start()
        assert dialog.timer.isActive()
        app.processEvents()
        dialog._cancel()
        assert dialog._outcome == "cancelled"
        assert sum(_candidate_totals(store).values()) == sum(johor_votes.values())

        dialog2 = ImportBallotDialog(store, str(path), win)
        dialog2._start()
        dialog2._progress = 98
        dialog2._tick()
        dialog2._tick()
        assert dialog2._outcome == "completed"
        assert store.data["stats"]["pending_reviews"] == 43
        dialog2._open_review()
        assert dialog2._outcome == "review"
        deadline = time.time() + 30
        while time.time() < deadline:
            app.processEvents()
            busy = any(
                dialog.ocr_worker is not None and dialog.ocr_worker.isRunning()
                for dialog in (dialog, dialog2)
            )
            if not busy:
                break
            time.sleep(0.02)

    report = []
    for page_id in ("dashboard", "scan", "review", "results", "audit", "settings"):
        win.show_page(page_id)
        app.processEvents()
        page = win.pages[page_id]
        scroll = None
        if isinstance(page, QScrollArea):
            scroll = page.verticalScrollBar().maximum()
        report.append(f"{page_id}: {page.width()}x{page.height()} vscroll={scroll}")
    print("\n".join(report))
    print("window", win.width(), win.height())
    print("ok")
    win.close()


if __name__ == "__main__":
    main()
