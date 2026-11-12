"""OCR and Negeri/DUN matching checks. OCR text is read by Tesseract, not stubbed."""

import os
import sys
import tempfile
import threading
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, QThread, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QTransform
from PySide6.QtWidgets import QApplication

from app.services.candidate_match import MISMATCH, compare_candidates
from app.services.location_match import HIGH, LOW, NOT_DETECTED, LocationMatch, match_location
from app.services.ocr_service import (
    INVALID_IMAGE,
    MISSING_EXECUTABLE,
    MISSING_LANGUAGE,
    OcrWorker,
    _coalesce_location_matches,
    extract_text,
    read_ballot_image,
    resolve_tesseract_cmd,
)


def _check_matcher() -> None:
    blank = match_location("   ")
    assert blank.status == NOT_DETECTED
    assert blank.negeri is None and blank.dun_code is None

    missing = match_location("This page has no constituency heading.")
    assert missing.status == NOT_DETECTED
    assert missing.negeri is None and missing.dun_code is None

    johor = match_location("Negeri Johor\nDUN N.01 Buloh Kasap")
    assert johor.status == HIGH
    assert johor.negeri == "Johor"
    assert johor.negeri_code == "JHR"
    assert johor.dun_code == "N.01"
    assert johor.dun_name == "Buloh Kasap"

    by_code = match_location("JHR N01")
    assert by_code.status == HIGH
    assert by_code.negeri == "Johor"
    assert by_code.dun_code == "N.01"
    assert by_code.dun_name == "Buloh Kasap"

    by_name = match_location("Johor — Buloh Kasap")
    assert by_name.status == HIGH
    assert by_name.dun_code == "N.01"

    incomplete = match_location("Johor")
    assert incomplete.negeri == "Johor"
    assert incomplete.negeri_status == HIGH
    assert incomplete.dun_code is None
    assert incomplete.dun_status == NOT_DETECTED
    assert incomplete.status == LOW

    several = match_location("Johor and Kedah")
    assert several.status == LOW
    assert several.negeri is None
    assert several.dun_code is None
    assert "More than one Negeri" in several.reason

    wrong = match_location("Johor N.99")
    assert wrong.negeri == "Johor"
    assert wrong.dun_code is None
    assert wrong.dun_status == LOW
    assert wrong.status == LOW
    assert "not a DUN" in wrong.reason

    conflict = match_location("Johor N.01 Jementah")
    assert conflict.negeri == "Johor"
    assert conflict.dun_code is None
    assert conflict.dun_status == LOW
    assert conflict.status == LOW
    assert "Jementah" in conflict.reason

    putrajaya = match_location("W.P. Putrajaya N.01")
    assert putrajaya.status == HIGH
    assert putrajaya.negeri == "W.P. Putrajaya"
    assert putrajaya.dun_code is None
    assert putrajaya.dun_name is None
    assert putrajaya.dun_status == NOT_DETECTED
    assert "parliamentary seats only" in putrajaya.reason

    code_only = match_location("N.01")
    assert code_only.negeri is None
    assert code_only.dun_code is None
    assert code_only.status == LOW
    assert "without a Negeri" in code_only.reason


_ARIAL_PATH = Path(r"C:\Windows\Fonts\arial.ttf")
_arial_family: str | None = None


def _arial_family_name() -> str:
    global _arial_family
    if _arial_family:
        return _arial_family
    if not _ARIAL_PATH.is_file():
        raise AssertionError(
            "OCR test setup error: Arial was not found at "
            f"{_ARIAL_PATH}. The synthetic ballot image cannot be drawn without that font file."
        )
    font_id = QFontDatabase.addApplicationFont(str(_ARIAL_PATH))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
    if not families:
        raise AssertionError(
            "OCR test setup error: Qt could not load "
            f"{_ARIAL_PATH}. Drawing without it would produce empty glyph boxes."
        )
    _arial_family = families[0]
    return _arial_family


def _paint_rows(path: Path, header: list[str], rows: list[str], *, marked: bool) -> None:
    image = QImage(1100, 1500, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont(_arial_family_name(), 28))
    for index, line in enumerate(header):
        painter.drawText(40, 80 + index * 70, line)
    for index, line in enumerate(rows):
        top = 460 + index * 220
        box = QRect(50, top, 140, 140)
        painter.setPen(QPen(Qt.GlobalColor.black, 4))
        painter.drawRect(box)
        if marked and index == 0:
            painter.setPen(QPen(Qt.GlobalColor.black, 12))
            painter.drawLine(box.left() + 24, box.top() + 24, box.right() - 24, box.bottom() - 24)
            painter.drawLine(box.right() - 24, box.top() + 24, box.left() + 24, box.bottom() - 24)
        painter.setPen(Qt.GlobalColor.black)
        painter.setFont(QFont(_arial_family_name(), 28))
        painter.drawText(230, top + 84, line)
    painter.end()
    assert image.save(str(path))


def _paint_ballot_lines(path: Path, lines: list[str]) -> None:
    image = QImage(900, 80 + 80 * len(lines), QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont(_arial_family_name(), 32))
    for index, line in enumerate(lines):
        painter.drawText(40, 70 + index * 70, line)
    painter.end()
    assert image.save(str(path))


def _paint_ballot(path: Path) -> None:
    image = QImage(900, 240, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setPen(Qt.GlobalColor.black)
    painter.setFont(QFont(_arial_family_name(), 36))
    painter.drawText(40, 90, "Johor")
    painter.drawText(40, 170, "N.01 Buloh Kasap")
    painter.end()
    assert image.save(str(path))


def _check_invalid(app: QApplication) -> None:
    del app
    missing = extract_text(r"C:\BallotVision\missing-ballot.png")
    assert missing.ok is False
    assert missing.text == ""
    assert missing.error_code == INVALID_IMAGE

    with tempfile.TemporaryDirectory() as folder:
        bad = Path(folder) / "notes.png"
        bad.write_text("not an image", encoding="utf-8")
        result = extract_text(str(bad))
    assert result.ok is False
    assert result.text == ""
    assert result.error_code == INVALID_IMAGE


def _check_missing_executable() -> None:
    with tempfile.TemporaryDirectory() as folder:
        image = Path(folder) / "ballot.png"
        _paint_ballot(image)
        result = extract_text(str(image), tesseract_cmd=str(Path(folder) / "missing-tesseract.exe"))
    assert result.ok is False
    assert result.text == ""
    assert result.error_code == MISSING_EXECUTABLE
    assert "does not install Tesseract" in result.error


def _check_missing_language() -> str:
    command = resolve_tesseract_cmd()
    if command is None:
        print("missing language: Tesseract is not installed, so the engine path was not run")
        return "not-run"
    with tempfile.TemporaryDirectory() as folder:
        image_dir = Path(folder)
        image = image_dir / "ballot.png"
        _paint_ballot(image)
        empty_data = image_dir / "tessdata"
        empty_data.mkdir()
        result = extract_text(str(image), tesseract_cmd=command, tessdata_dir=str(empty_data))
    assert result.ok is False
    assert result.text == ""
    assert result.error_code == MISSING_LANGUAGE
    print("missing language: Tesseract returned", result.error_code)
    return "passed"


def _check_conflicting_location_passes() -> None:
    first = LocationMatch("Johor", "JHR", "N.01", "Buloh Kasap", HIGH, HIGH, HIGH, "Matched")
    second = LocationMatch("Kedah", "KDH", "N.01", "Ayer Hangat", HIGH, HIGH, HIGH, "Matched")
    merged = _coalesce_location_matches([first, second])
    assert merged.status == LOW
    assert merged.negeri is None
    assert merged.dun_code is None
    assert "conflicting" in merged.reason.casefold()


def _paint_variant(
    path: Path,
    *,
    width: int,
    height: int,
    header_y: int,
    low_contrast: bool = False,
    rotation: float = 0.0,
    header_lines: tuple[str, ...] = ("Johor", "N.01 Buloh Kasap"),
) -> None:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    if low_contrast:
        image.fill(QColor(245, 245, 245))
    painter = QPainter(image)
    painter.setPen(QColor(40, 40, 40) if not low_contrast else QColor(100, 100, 100))
    font_size = 38 if width >= 1200 else 28
    if low_contrast:
        font_size = max(18, font_size - 8)
    painter.setFont(QFont(_arial_family_name(), font_size))
    for index, line in enumerate(header_lines):
        painter.drawText(60, header_y + index * 70, line)
    painter.end()
    if rotation:
        transform = QTransform()
        transform.translate(width / 2, height / 2)
        transform.rotate(rotation)
        transform.translate(-width / 2, -height / 2)
        image = image.transformed(transform, Qt.TransformationMode.SmoothTransformation)
    assert image.save(str(path))


def _check_location_preprocessing_variants() -> None:
    command = resolve_tesseract_cmd()
    if command is None:
        print("location preprocessing: skipped because Tesseract is not installed")
        return
    with tempfile.TemporaryDirectory() as folder:
        cases = [
            (Path(folder) / "small.png", (680, 240), 80, False, 0.0),
            (Path(folder) / "wide.png", (1600, 1000), 110, False, 0.0),
            (Path(folder) / "rotated.png", (1000, 720), 120, False, 8.0),
            (Path(folder) / "low-contrast.png", (1100, 700), 150, True, 0.0),
            (Path(folder) / "low-header.png", (1000, 740), 260, False, 0.0),
        ]
        for path, (width, height), header_y, low_contrast, rotation in cases:
            _paint_variant(
                path,
                width=width,
                height=height,
                header_y=header_y,
                low_contrast=low_contrast,
                rotation=rotation,
                header_lines=("Johor", "N.01 Buloh Kasap"),
            )
            reading = read_ballot_image(str(path), tesseract_cmd=command)
            if reading.ocr.error_code == MISSING_LANGUAGE:
                print("location preprocessing: skipped because language data is missing")
                return
            assert reading.ocr.ok, reading.ocr.error
            assert reading.location.negeri == "Johor", (path.name, reading.location.reason)
            assert reading.location.dun_code == "N.01", (path.name, reading.location.reason)
            assert reading.location.status == HIGH, (path.name, reading.location.reason)

        ambiguous = Path(folder) / "ambiguous-header.png"
        _paint_variant(
            ambiguous,
            width=1100,
            height=700,
            header_y=120,
            low_contrast=False,
            rotation=0.0,
            header_lines=("Johor", "N.99 Not A DUN"),
        )
        ambiguous_reading = read_ballot_image(str(ambiguous), tesseract_cmd=command)
        assert ambiguous_reading.location.status != HIGH
        assert ambiguous_reading.location.negeri in {"Johor", None}

        incomplete = Path(folder) / "incomplete-location.png"
        _paint_variant(
            incomplete,
            width=900,
            height=500,
            header_y=110,
            low_contrast=False,
            rotation=0.0,
            header_lines=("Johor",),
        )
        incomplete_reading = read_ballot_image(str(incomplete), tesseract_cmd=command)
        assert incomplete_reading.location.negeri == "Johor"
        assert incomplete_reading.location.dun_code is None
        assert incomplete_reading.location.status == LOW


def _check_valid_image() -> str:
    command = resolve_tesseract_cmd()
    if command is None:
        print("valid image: skipped because Tesseract is not installed")
        return "skipped"
    with tempfile.TemporaryDirectory() as folder:
        image = Path(folder) / "ballot.png"
        _paint_ballot(image)
        reading = read_ballot_image(str(image), tesseract_cmd=command)
    if reading.ocr.error_code == MISSING_LANGUAGE:
        print("valid image: skipped because language data is missing:", reading.ocr.error)
        return "skipped"
    assert reading.ocr.ok, reading.ocr.error
    assert reading.ocr.text.strip(), (
        f"error_code={reading.ocr.error_code!r} text={reading.ocr.text!r}"
    )
    folded = reading.ocr.text.casefold()
    assert "johor" in folded, reading.ocr.text
    assert "buloh" in folded or "n.01" in folded or "n. 01" in folded, reading.ocr.text
    assert reading.location.negeri == "Johor"
    assert reading.location.dun_code == "N.01"
    assert reading.location.dun_name == "Buloh Kasap"
    print("valid image text:", " ".join(reading.ocr.text.split()))
    _check_marked_and_unmarked(command)
    _check_location_preprocessing_variants()
    return "passed"


def _check_marked_and_unmarked(command: str) -> None:
    header = ["SURUHANJAYA PILIHAN RAYA MALAYSIA", "NEGERI JOHOR", "N.01 BULOH KASAP"]
    with tempfile.TemporaryDirectory() as folder:
        unmarked = Path(folder) / "unmarked.png"
        marked = Path(folder) / "marked.png"
        ambiguous = Path(folder) / "ambiguous.png"
        _paint_rows(unmarked, header, ["AMALIA SURIA", "RIZAL PURNAMA"], marked=False)
        _paint_rows(marked, header, ["AMALIA SURIA", "KEDAH N.02 JEMENTAH"], marked=True)
        _paint_ballot_lines(ambiguous, header + ["KEDAH N.02 JEMENTAH"])
        plain = read_ballot_image(str(unmarked), tesseract_cmd=command)
        crossed = read_ballot_image(str(marked), tesseract_cmd=command)
        mixed = read_ballot_image(str(ambiguous), tesseract_cmd=command)
    for reading in (plain, crossed, mixed):
        assert reading.ocr.ok, reading.ocr.error
        folded = reading.ocr.text.casefold()
        assert "johor" in folded, reading.ocr.text
        assert "buloh" in folded, reading.ocr.text
    assert "amalia" in plain.ocr.text.casefold()
    assert plain.location.negeri == "Johor"
    assert plain.location.dun_name == "Buloh Kasap"
    assert plain.location.status == HIGH
    crossed_text = crossed.ocr.text.casefold()
    assert "kedah" in crossed_text, crossed.ocr.text
    assert "amalia" in crossed_text, crossed.ocr.text
    assert crossed.location.negeri == "Johor"
    assert crossed.location.dun_code == "N.01"
    assert crossed.location.dun_name == "Buloh Kasap"
    assert crossed.location.status == HIGH
    assert "kedah" not in (crossed.ocr.header_text or "").casefold()
    assert "kedah" in mixed.ocr.text.casefold()
    assert mixed.location.negeri is None
    assert mixed.location.status != HIGH


def _check_candidate_names() -> None:
    official = ["Amalia Suria", "Rizal Purnama", "Nora Bentara", "Faizal Ombak"]
    exact = compare_candidates(["Amalia Suria"], official)
    assert exact.status == "consistent"
    assert exact.matched == ("Amalia Suria",)
    assert exact.unknown == ()
    partial = compare_candidates(["Amalia"], official)
    assert partial.status == MISMATCH
    assert partial.matched == ()
    assert partial.unknown == ("Amalia",)
    foreign = compare_candidates(["Ghost Person"], official)
    assert foreign.mismatched
    assert foreign.unknown == ("Ghost Person",)
    assert "Amalia Suria" not in foreign.matched


def _check_worker(app: QApplication) -> None:
    with tempfile.TemporaryDirectory() as folder:
        image = Path(folder) / "ballot.png"
        _paint_ballot(image)
        worker = OcrWorker(str(image))
        box: dict = {}

        def _store(reading) -> None:
            box["reading"] = reading

        worker.completed.connect(_store)
        worker.start()
        assert worker.wait(15000)
        app.processEvents()
    assert "reading" in box
    assert box["reading"].ocr.thread_id != threading.get_ident()
    assert isinstance(worker, QThread)


def main() -> None:
    app = QApplication(sys.argv)
    _check_matcher()
    _check_invalid(app)
    _check_missing_executable()
    language = _check_missing_language()
    valid = _check_valid_image()
    _check_candidate_names()
    _check_worker(app)
    print(f"ocr checks ok (language={language}, valid-image={valid})")


if __name__ == "__main__":
    main()
