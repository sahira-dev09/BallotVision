"""Candidate mark recognition uses the pixels in the image, then the counting rules."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QTransform
from PySide6.QtWidgets import QApplication

from app.core.candidates import build_candidate_records
from app.core.store import Store
from app.services.mark_recognition import (
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    REASON_LOCATION,
    REASON_MULTIPLE,
    REASON_NONE,
    REASON_OTHER_DUN,
    REASON_OUTSIDE,
    REASON_UNCLEAR,
    REASON_UNMATCHED,
    STATUS_MULTIPLE,
    STATUS_NONE,
    STATUS_OUTSIDE,
    STATUS_SINGLE,
    STATUS_UNCLEAR,
    adjudicate,
    recognize_marks,
)
from app.services.ocr_service import read_ballot_image
from app.widgets.ocr_panel import fields_from_inspection

_ARIAL = Path(r"C:\Windows\Fonts\arial.ttf")


def _font() -> str:
    font_id = QFontDatabase.addApplicationFont(str(_ARIAL))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise AssertionError(f"OCR test setup error: Qt could not load {_ARIAL}.")
    return families[0]


def _paint(path: Path, family: str, marked: set[int], names: list[str] | None = None, *, faint=False, outside=False, partial=False, header=None) -> None:
    image = QImage(1100, 1400, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont(family, 28))
    for index, line in enumerate(header or ["NEGERI JOHOR", "N.01 BULOH KASAP"]):
        painter.drawText(40, 80 + index * 60, line)
    labels = names or ["AMALIA SURIA", "RIZAL PURNAMA", "NORA BENTARA", "FAIZAL OMBAK"]
    for index, name in enumerate(labels):
        top = 280 + index * 220
        box = QRect(60, top, 150, 150)
        painter.setPen(QPen(Qt.GlobalColor.black, 4))
        painter.drawRect(box)
        painter.setPen(Qt.GlobalColor.black)
        painter.setFont(QFont(family, 28))
        painter.drawText(250, top + 90, name)
        if index not in marked:
            continue
        color = QColor(150, 150, 150) if faint else Qt.GlobalColor.black
        painter.setPen(QPen(color, 6 if faint else 14))
        inset = 28
        painter.drawLine(box.left() + inset, box.top() + inset, box.right() - inset, box.bottom() - inset)
        if not partial:
            painter.drawLine(box.right() - inset, box.top() + inset, box.left() + inset, box.bottom() - inset)
    if outside:
        painter.setPen(QPen(Qt.GlobalColor.black, 14))
        painter.drawLine(760, 520, 920, 680)
        painter.drawLine(920, 520, 760, 680)
    painter.end()
    assert image.save(str(path))


def _paint_quality(
    path: Path,
    family: str,
    *,
    w: int = 1100,
    h: int = 1400,
    stroke: int = 14,
    tilt: int = 0,
    rotate: int = 0,
    paper: QColor | Qt.GlobalColor = Qt.GlobalColor.white,
    ink: QColor | Qt.GlobalColor = Qt.GlobalColor.black,
) -> None:
    """Generated ballot with a controllable X, used for sensitivity cases."""
    image = QImage(w, h, QImage.Format.Format_RGB32)
    image.fill(paper)
    painter = QPainter(image)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont(family, max(14, int(28 * w / 1100))))
    painter.drawText(int(40 * w / 1100), int(80 * h / 1400), "NEGERI JOHOR")
    painter.drawText(int(40 * w / 1100), int(140 * h / 1400), "N.01 BULOH KASAP")
    labels = ["AMALIA SURIA", "RIZAL PURNAMA", "NORA BENTARA", "FAIZAL OMBAK"]
    box_size = max(36, int(150 * w / 1100))
    for index, name in enumerate(labels):
        top = int((280 + index * 220) * h / 1400)
        left = int(60 * w / 1100)
        box = QRect(left, top, box_size, box_size)
        painter.setPen(QPen(Qt.GlobalColor.black, max(2, int(4 * w / 1100))))
        painter.drawRect(box)
        painter.setPen(Qt.GlobalColor.black)
        painter.setFont(QFont(family, max(12, int(28 * w / 1100))))
        painter.drawText(left + box_size + int(30 * w / 1100), top + box_size // 2, name)
        if index != 0:
            continue
        painter.save()
        painter.translate(box.center())
        painter.rotate(tilt)
        painter.translate(-box.center())
        painter.setPen(QPen(ink, stroke))
        inset = max(6, box_size // 5)
        painter.drawLine(box.left() + inset, box.top() + inset, box.right() - inset, box.bottom() - inset)
        painter.drawLine(box.right() - inset, box.top() + inset, box.left() + inset, box.bottom() - inset)
        painter.restore()
    painter.end()
    if rotate:
        image = image.transformed(QTransform().rotate(rotate), Qt.TransformationMode.SmoothTransformation)
    assert image.save(str(path))


def _votes(store: Store) -> dict:
    return {item["candidate_id"]: int(item["vote_count"]) for item in store.data["candidates"]}


def main() -> None:
    app = QApplication(sys.argv)
    family = _font()
    official = build_candidate_records(state_code="JHR", dun_code="N.01")
    with tempfile.TemporaryDirectory() as folder_name:
        folder = Path(folder_name)
        images = {
            "a": dict(marked={0}),
            "b": dict(marked={1}),
            "none": dict(marked=set()),
            "multi": dict(marked={0, 2}),
            "faint": dict(marked={0}, faint=True),
            "outside": dict(marked=set(), outside=True),
            "partial": dict(marked={0}, partial=True),
            "unknown": dict(marked={0}, names=["GHOST PERSON", "RIZAL PURNAMA", "NORA BENTARA", "FAIZAL OMBAK"]),
            "low": dict(marked={0}, header=["N.01"]),
        }
        paths = {}
        marks = {}
        for name, options in images.items():
            paths[name] = folder / f"{name}.png"
            _paint(paths[name], family, **options)
            marks[name] = recognize_marks(str(paths[name]))

        assert marks["a"].status == STATUS_SINGLE and marks["a"].confidence == HIGH_CONFIDENCE
        assert "amalia suria" in marks["a"].row_text.casefold()
        assert marks["b"].status == STATUS_SINGLE
        assert "rizal purnama" in marks["b"].row_text.casefold()
        assert marks["a"].row_text.casefold() != marks["b"].row_text.casefold()
        assert marks["none"].status == STATUS_NONE and marks["none"].reason == REASON_NONE
        assert marks["multi"].status == STATUS_MULTIPLE and marks["multi"].reason == REASON_MULTIPLE
        assert marks["faint"].status == STATUS_UNCLEAR and marks["faint"].confidence == LOW_CONFIDENCE
        assert marks["partial"].status == STATUS_UNCLEAR and marks["partial"].reason == REASON_UNCLEAR
        assert marks["outside"].status == STATUS_OUTSIDE and marks["outside"].reason == REASON_OUTSIDE
        assert "X-mark detection" in marks["none"].diagnosis
        assert "more than one" in marks["multi"].diagnosis.casefold()
        assert "not a clear X" in marks["faint"].diagnosis
        assert "Candidate name extraction" in marks["a"].diagnosis

        quality = {
            "thin": dict(stroke=2),
            "thick": dict(stroke=28),
            "tilt": dict(tilt=18),
            "small": dict(w=480, h=640, stroke=4),
            "large": dict(w=2200, h=2800, stroke=22),
            "rotated": dict(rotate=4),
            "photo": dict(paper=QColor(210, 210, 205), ink=QColor(40, 40, 40), stroke=8),
        }
        for name, options in quality.items():
            path = folder / f"quality-{name}.png"
            _paint_quality(path, family, **options)
            found = recognize_marks(str(path))
            assert found.status == STATUS_SINGLE and found.confidence == HIGH_CONFIDENCE, (name, found.status, found.diagnosis)
            assert "amalia suria" in found.row_text.casefold(), (name, found.row_text)
            assert found.box_count == 4, (name, found.box_count)
        rotated_reading = read_ballot_image(str(folder / "quality-rotated.png"))
        assert rotated_reading.location.status == "High confidence"
        assert rotated_reading.location.negeri == "Johor"
        assert rotated_reading.location.dun_code == "N.01"

        counted_a = adjudicate(
            ocr_ok=True,
            location_status="High confidence",
            negeri="Johor",
            dun_code="N.01",
            dun_applicable_seat=True,
            mark=marks["a"],
            official=official,
        )
        counted_b = adjudicate(
            ocr_ok=True,
            location_status="High confidence",
            negeri="Johor",
            dun_code="N.01",
            dun_applicable_seat=True,
            mark=marks["b"],
            official=official,
        )
        assert counted_a.counted and counted_a.candidate_name == "Amalia Suria"
        assert counted_b.counted and counted_b.candidate_name == "Rizal Purnama"
        assert counted_a.candidate_id != counted_b.candidate_id
        for name in ("none", "multi", "faint", "partial", "outside"):
            decision = adjudicate(
                ocr_ok=True,
                location_status="High confidence",
                negeri="Johor",
                dun_code="N.01",
                dun_applicable_seat=True,
                mark=marks[name],
                official=official,
            )
            assert decision.counted is False
            assert decision.review is True
            assert decision.candidate_name == ""

        unknown = adjudicate(
            ocr_ok=True,
            location_status="High confidence",
            negeri="Johor",
            dun_code="N.01",
            dun_applicable_seat=True,
            mark=marks["unknown"],
            official=official,
        )
        assert unknown.counted is False
        assert unknown.reason == REASON_UNMATCHED
        assert "ghost person" in marks["unknown"].row_text.casefold()

        other_roster = build_candidate_records(state_code="JHR", dun_code="N.02")
        other = adjudicate(
            ocr_ok=True,
            location_status="High confidence",
            negeri="Johor",
            dun_code="N.01",
            dun_applicable_seat=True,
            mark=marks["a"],
            official=other_roster,
        )
        assert other.counted is False
        assert other.reason == REASON_OTHER_DUN

        low = adjudicate(
            ocr_ok=True,
            location_status="Low confidence",
            negeri="Johor",
            dun_code="N.01",
            dun_applicable_seat=True,
            mark=marks["a"],
            official=official,
        )
        assert low.counted is False
        assert low.reason == REASON_LOCATION
        assert low.mark_confidence == HIGH_CONFIDENCE

        reading = read_ballot_image(str(paths["low"]))
        assert reading.location.status != "High confidence"
        low_fields = fields_from_inspection(reading, marks["low"], source_path=str(paths["low"]))
        assert low_fields["suggested_negeri"] == ""
        store = Store()
        before = _votes(store)
        assert store.complete_import_processing(1, source_paths=[str(paths["low"])], notify=False, reading=low_fields) == "review"
        assert _votes(store) == before
        assert store.data["flagged"][0]["reason"] == REASON_LOCATION

        clear = read_ballot_image(str(paths["a"]))
        fields = fields_from_inspection(clear, marks["a"], source_path=str(paths["a"]))
        assert fields["match_status"] == "High confidence"
        assert fields["mark_confidence"] == HIGH_CONFIDENCE
        assert store.complete_import_processing(1, source_paths=[str(paths["a"])], notify=False, reading=fields) == "counted"
        after = _votes(store)
        assert after["CAN-D01"] == before["CAN-D01"] + 1
        assert after["CAN-D02"] == before["CAN-D02"]
        record = store.data["location_sessions"]["Johor|N.01"]["vote_records"][0]
        assert record["candidate_id"] == "CAN-D01"
        assert record["candidate_name"] == "Amalia Suria"
        assert record["image_ref"] == str(paths["a"])
        assert record["negeri"] == "Johor"
        assert record["dun_code"] == "N.01"
        assert record["location_confidence"] == "High confidence"
        assert record["mark_confidence"] == HIGH_CONFIDENCE
        assert record["status"] == "Counted"
        assert record["timestamp"]
        assert store.complete_import_processing(1, source_paths=[str(paths["a"])], notify=False, reading=fields) == "duplicate"
        assert _votes(store) == after
        assert len(store.data["location_sessions"]["Johor|N.01"]["vote_records"]) == 1
        assert str(paths["a"]) not in {item.get("source_path") for item in store.data["flagged"]}

    print("mark checks ok")


if __name__ == "__main__":
    main()
