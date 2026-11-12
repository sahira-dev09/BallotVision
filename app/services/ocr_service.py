"""Read printed text from a ballot image with Tesseract.

The Python package does not include the Tesseract program or the eng/msa
language files. Set BALLOTVISION_TESSERACT_CMD to the full path of
tesseract.exe when it is not on PATH. See docs/tesseract-windows.md.

OCR runs on a QThread so the Qt UI thread is not blocked. ImportBallotDialog
and ScanPage can both call read_ballot_image(); there is one implementation.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QImage, QImageReader, QPainter, QTransform

from app.services.location_match import HIGH, LOW, NOT_DETECTED, LocationMatch, match_location

LANGUAGES = ("eng", "msa")
MISSING_EXECUTABLE = "missing_executable"
MISSING_LANGUAGE = "missing_language"
INVALID_IMAGE = "invalid_image"
OCR_FAILED = "ocr_failed"
OCR_TIMEOUT_MESSAGE = "OCR timed out before the ballot location could be read."
INSPECTION_LIMIT_SECONDS = 20
_OCR_LONG_SIDE = 1800
_PAGE_OCR_CAP = 12
_HEADER_OCR_CAP = 6
_LOCK = threading.Lock()
_LANGUAGE_CACHE: dict[tuple[str, str], tuple[str, ...]] = {}
_PROC_LOCK = threading.Lock()
_ACTIVE_PROCS: list = []
_OCR_TRACKING = False


@dataclass(frozen=True)
class OcrResult:
    ok: bool
    text: str
    languages: tuple[str, ...]
    mean_confidence: float | None
    error: str
    error_code: str
    thread_id: int
    header_text: str | None = None


@dataclass(frozen=True)
class BallotReading:
    """One image reading. Location suggestions are not confirmed election data."""

    ocr: OcrResult
    location: LocationMatch


class OcrWorker(QThread):
    """Background OCR. Connect to completed; do not call extract_text from the UI thread."""

    completed = Signal(object)

    def __init__(self, image_path: str, parent=None) -> None:
        super().__init__(parent)
        self.image_path = image_path

    def run(self) -> None:  # noqa: N802
        self.completed.emit(read_ballot_image(self.image_path))


def install_ocr_process_tracking() -> None:
    """Remember Tesseract processes so application shutdown can let the worker return.

    The QThread is not killed. Only the external OCR process is asked to exit,
    and only when the application is closing.
    """
    global _OCR_TRACKING
    if _OCR_TRACKING:
        return
    try:
        import pytesseract.pytesseract as pytesseract_module
    except ImportError:
        return
    original = pytesseract_module.subprocess.Popen

    def tracking_popen(*args, **kwargs):
        process = original(*args, **kwargs)
        command = args[0] if args else kwargs.get("args", "")
        rendered = command if isinstance(command, str) else " ".join(str(part) for part in command)
        if "tesseract" in rendered.casefold():
            with _PROC_LOCK:
                _ACTIVE_PROCS.append(process)
        return process

    pytesseract_module.subprocess.Popen = tracking_popen
    _OCR_TRACKING = True


def cancel_active_ocr() -> None:
    """Ask in-flight Tesseract processes to exit so their QThread can finish."""
    install_ocr_process_tracking()
    with _PROC_LOCK:
        processes = [process for process in _ACTIVE_PROCS if process.poll() is None]
        _ACTIVE_PROCS[:] = processes
    for process in processes:
        if process.poll() is not None:
            continue
        process.terminate()
        try:
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


def read_ballot_image(
    image_path: str,
    *,
    tesseract_cmd: str | None = None,
    tessdata_dir: str | None = None,
    deadline: float | None = None,
) -> BallotReading:
    """OCR one validated path, then match Negeri and DUN. Does not change the store."""
    if deadline is None:
        deadline = time.monotonic() + INSPECTION_LIMIT_SECONDS
    ocr = extract_text(
        image_path,
        tesseract_cmd=tesseract_cmd,
        tessdata_dir=tessdata_dir,
        deadline=deadline,
    )
    if not ocr.ok:
        location = LocationMatch(
            negeri=None,
            negeri_code=None,
            dun_code=None,
            dun_name=None,
            status=NOT_DETECTED,
            negeri_status=NOT_DETECTED,
            dun_status=NOT_DETECTED,
            reason=ocr.error,
        )
        return BallotReading(ocr=ocr, location=location)

    candidates = _location_text_candidates(image_path, ocr=ocr, deadline=deadline, tesseract_cmd=tesseract_cmd, tessdata_dir=tessdata_dir)
    matches = [match_location(text) for text in candidates if text and text.strip()]
    location = _coalesce_location_matches(matches)
    return BallotReading(ocr=ocr, location=location)


def extract_text(
    image_path: str,
    *,
    tesseract_cmd: str | None = None,
    tessdata_dir: str | None = None,
    deadline: float | None = None,
) -> OcrResult:
    thread_id = threading.get_ident()
    path = Path(image_path)
    if not path.is_file():
        return _failure(INVALID_IMAGE, "File could not be found.", thread_id)
    reader = QImageReader(str(path))
    image = reader.read()
    if image.isNull():
        detail = reader.errorString() or "This file could not be opened as an image."
        return _failure(INVALID_IMAGE, detail, thread_id)

    command = resolve_tesseract_cmd(tesseract_cmd)
    if command is None or not Path(command).is_file():
        return _failure(
            MISSING_EXECUTABLE,
            "Tesseract OCR was not found. Install the Tesseract program and set "
            "BALLOTVISION_TESSERACT_CMD to tesseract.exe. Installing pytesseract does not install Tesseract.",
            thread_id,
        )

    try:
        install_ocr_process_tracking()
        import pytesseract
    except ImportError:
        return _failure(
            MISSING_EXECUTABLE,
            "The pytesseract package is not installed in this Python environment.",
            thread_id,
        )

    if deadline is None:
        deadline = time.monotonic() + INSPECTION_LIMIT_SECONDS
    config = _tesseract_config(tessdata_dir)
    prepared = _write_prepared(image)
    ocr_path = prepared or path
    try:
        with _LOCK:
            pytesseract.pytesseract.tesseract_cmd = command
            available = _cached_languages(pytesseract, command, config, tessdata_dir)
            missing = [lang for lang in LANGUAGES if lang not in available]
            if missing:
                return _failure(
                    MISSING_LANGUAGE,
                    "Tesseract is missing language data: " + ", ".join(missing) + ". Install eng and msa.",
                    thread_id,
                )
            page_timeout = _seconds_left(deadline, _PAGE_OCR_CAP)
            if page_timeout < 1:
                return _failure(OCR_FAILED, OCR_TIMEOUT_MESSAGE, thread_id)
            text = pytesseract.image_to_string(
                str(ocr_path),
                lang="+".join(LANGUAGES),
                config=config,
                timeout=page_timeout,
            )
            confidence = None
            header_timeout = _seconds_left(deadline, _HEADER_OCR_CAP)
            header_text = (
                _header_text(pytesseract, ocr_path, config, timeout=header_timeout)
                if header_timeout >= 1
                else None
            )
    except pytesseract.TesseractNotFoundError:
        return _failure(
            MISSING_EXECUTABLE,
            f"Tesseract OCR could not be started at {command}.",
            thread_id,
        )
    except pytesseract.TesseractError as exc:
        message = getattr(exc, "message", "") or str(exc)
        if _is_language_error(message):
            return _failure(MISSING_LANGUAGE, f"Tesseract language data could not be loaded. {message}", thread_id)
        if _is_image_error(message):
            return _failure(INVALID_IMAGE, "Tesseract could not read this image.", thread_id)
        return _failure(OCR_FAILED, f"Tesseract failed. {message}", thread_id)
    except RuntimeError as exc:
        if "timeout" in str(exc).casefold():
            return _failure(OCR_FAILED, OCR_TIMEOUT_MESSAGE, thread_id)
        return _failure(OCR_FAILED, f"Tesseract failed. {exc}", thread_id)
    except Exception as exc:
        return _failure(OCR_FAILED, f"Tesseract failed. {exc}", thread_id)
    finally:
        if prepared is not None:
            prepared.unlink(missing_ok=True)

    return OcrResult(
        ok=True,
        text=text or "",
        languages=LANGUAGES,
        mean_confidence=confidence,
        error="",
        error_code="",
        thread_id=thread_id,
        header_text=header_text,
    )


def resolve_tesseract_cmd(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    env_cmd = os.environ.get("BALLOTVISION_TESSERACT_CMD", "").strip()
    if env_cmd:
        return env_cmd
    found = shutil.which("tesseract")
    if found:
        return found
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(program_files) / "Tesseract-OCR" / "tesseract.exe",
        Path(program_files_x86) / "Tesseract-OCR" / "tesseract.exe",
        Path(local) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _coalesce_location_matches(matches: list[LocationMatch]) -> LocationMatch:
    """Combine several OCR passes without weakening the existing match rules.

    A location is accepted only when it remains consistent across the valid OCR
    passes, and the final result still satisfies `match_location()`'s strict
    high-confidence validation.
    """
    if not matches:
        return LocationMatch(
            negeri=None,
            negeri_code=None,
            dun_code=None,
            dun_name=None,
            status=NOT_DETECTED,
            negeri_status=NOT_DETECTED,
            dun_status=NOT_DETECTED,
            reason="No location text was available to match.",
        )

    high = [match for match in matches if match.status == HIGH]
    if high:
        keys = {
            (
                match.negeri or "",
                match.negeri_code or "",
                match.dun_code or "",
                match.dun_name or "",
            )
            for match in high
        }
        if len(keys) > 1:
            return LocationMatch(
                negeri=None,
                negeri_code=None,
                dun_code=None,
                dun_name=None,
                status=LOW,
                negeri_status=LOW,
                dun_status=LOW,
                reason="Conflicting OCR location results were detected across multiple passes; the location is ambiguous and no vote was counted.",
            )
        return high[0]

    low = [match for match in matches if match.status == LOW]
    if low:
        keys = {
            (
                match.negeri or "",
                match.negeri_code or "",
                match.dun_code or "",
                match.dun_name or "",
            )
            for match in low
        }
        if len(keys) > 1:
            return LocationMatch(
                negeri=None,
                negeri_code=None,
                dun_code=None,
                dun_name=None,
                status=LOW,
                negeri_status=LOW,
                dun_status=LOW,
                reason="Conflicting OCR location results were detected across multiple passes; the location is ambiguous and no vote was counted.",
            )
        return low[0]

    return matches[0]


def _location_text_candidates(
    image_path: str,
    *,
    ocr: OcrResult,
    deadline: float,
    tesseract_cmd: str | None = None,
    tessdata_dir: str | None = None,
) -> list[str]:
    """Collect multiple OCR text candidates for the ballot header.

    The full page OCR remains in play, but additional header crops are checked so
    a shifted or undersized location line is not missed. The final decision still
    relies on the existing matcher and high-confidence validation.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    def add(value: str | None) -> None:
        if value is None:
            return
        text = (value or "").strip()
        if text and text.casefold() not in seen:
            candidates.append(text)
            seen.add(text.casefold())

    add(ocr.text)
    add(ocr.header_text)

    try:
        import pytesseract
    except ImportError:
        return candidates

    image = QImage(str(image_path))
    if image.isNull():
        return candidates

    width = image.width()
    height = image.height()
    if width <= 0 or height <= 0:
        return candidates

    config = _tesseract_config(tessdata_dir)
    timeout = _seconds_left(deadline, _HEADER_OCR_CAP)
    if timeout < 1:
        return candidates

    band_top = _candidate_band_top(image)
    if band_top is None:
        band_top = max(28, int(height * 0.28))
    y_limits = [
        min(height, max(32, band_top)),
        min(height, max(band_top, int(height * 0.34))),
        min(height, max(int(height * 0.18), int(height * 0.46))),
    ]
    for y_end in sorted(set(y_limits)):
        if y_end <= 0:
            continue
        crop = image.copy(0, 0, width, y_end)
        if crop.isNull() or crop.height() < 24:
            continue
        target = _write_qimage(crop)
        if not target:
            continue
        try:
            text = pytesseract.image_to_string(
                target,
                lang="+".join(LANGUAGES),
                config=config,
                timeout=max(1.0, timeout),
            )
        except (pytesseract.TesseractError, RuntimeError, OSError):
            continue
        finally:
            Path(target).unlink(missing_ok=True)
        add(text)
    return candidates


def _write_qimage(image: QImage) -> str:
    handle = tempfile.NamedTemporaryFile(prefix="ballotvision-location-crop-", suffix=".png", delete=False)
    handle.close()
    target = Path(handle.name)
    if not image.save(str(target), "PNG"):
        target.unlink(missing_ok=True)
        return ""
    return str(target)


def _location_source(ocr: OcrResult) -> str:
    """Prefer the header reading when candidate marks make the full page ambiguous.

    The displayed text stays the full-page reading. This only chooses which
    real OCR string is passed to the Negeri/DUN matcher.
    """
    full_text = ocr.text or ""
    header_text = ocr.header_text
    if header_text is None:
        return full_text
    header_match = match_location(header_text)
    if header_match.status == HIGH and header_match.negeri_status == HIGH:
        return header_text
    full_match = match_location(full_text)
    header_conflicts = (
        header_match.negeri
        and header_match.negeri_status == HIGH
        and full_match.negeri
        and header_match.negeri != full_match.negeri
    )
    if full_match.status == HIGH and full_match.negeri_status == HIGH and not header_conflicts:
        return full_text
    return header_text


def _seconds_left(deadline: float, cap: float) -> float:
    return max(0.0, min(cap, deadline - time.monotonic()))


def _cached_languages(pytesseract, command: str, config: str, tessdata_dir: str | None) -> tuple[str, ...]:
    key = (command, tessdata_dir or "")
    cached = _LANGUAGE_CACHE.get(key)
    if cached is not None:
        return cached
    found = tuple(pytesseract.get_languages(config=config))
    if all(lang in found for lang in LANGUAGES):
        _LANGUAGE_CACHE[key] = found
    return found


def _header_text(pytesseract, image_path: Path, config: str, timeout: float = 6) -> str | None:
    """OCR the area above the first candidate box, when one is visible.

    Returns None when no box is found, so unmarked pages keep a single reading.
    """
    image = QImage(str(image_path))
    if image.isNull():
        return None
    band_top = _candidate_band_top(image)
    if band_top is None:
        return None
    crop = image.copy(0, 0, image.width(), band_top)
    if crop.isNull() or crop.height() < 24:
        return None
    handle = tempfile.NamedTemporaryFile(prefix="ballotvision-ocr-header-", suffix=".png", delete=False)
    handle.close()
    target = Path(handle.name)
    try:
        if not crop.save(str(target), "PNG"):
            return None
        header = pytesseract.image_to_string(
            str(target),
            lang="+".join(LANGUAGES),
            config=config,
            timeout=max(1, timeout),
        )
    except (pytesseract.TesseractError, RuntimeError, OSError):
        return None
    finally:
        target.unlink(missing_ok=True)
    return header or ""


def _candidate_band_top(image: QImage) -> int | None:
    """Y position of the first large mark or candidate box, in pixels.

    Text lines are short. A candidate box or a thick X is a tall, compact
    dark shape. The returned Y is the top of that shape so the header crop
    does not include the mark.
    """
    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    width = gray.width()
    height = gray.height()
    if width < 40 or height < 40:
        return None
    raw = gray.constBits().tobytes()
    stride = gray.bytesPerLine()
    step = 2 if width * height <= 2_500_000 else 3
    cols = (width + step - 1) // step
    rows = (height + step - 1) // step
    dark = bytearray(cols * rows)
    for row in range(rows):
        y = min(height - 1, row * step)
        base = y * stride
        for col in range(cols):
            x = min(width - 1, col * step)
            if raw[base + x] < 72:
                dark[row * cols + col] = 1
    seen = bytearray(cols * rows)
    minimum_side = max(12, int(min(width, height) * 0.045))
    earliest: int | None = None
    for start in range(cols * rows):
        if not dark[start] or seen[start]:
            continue
        stack = [start]
        seen[start] = 1
        min_x = max_x = start % cols
        min_y = max_y = start // cols
        count = 0
        while stack:
            current = stack.pop()
            count += 1
            cx = current % cols
            cy = current // cols
            if cx < min_x:
                min_x = cx
            elif cx > max_x:
                max_x = cx
            if cy < min_y:
                min_y = cy
            elif cy > max_y:
                max_y = cy
            for nxt, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if nxt < 0 or ny < 0 or nxt >= cols or ny >= rows:
                    continue
                index = ny * cols + nxt
                if dark[index] and not seen[index]:
                    seen[index] = 1
                    stack.append(index)
        if count < 10:
            continue
        pixel_w = (max_x - min_x + 1) * step
        pixel_h = (max_y - min_y + 1) * step
        top = min_y * step
        if pixel_w < minimum_side or pixel_h < minimum_side:
            continue
        if pixel_w > width * 0.96 and pixel_h > height * 0.96:
            continue
        ratio = pixel_w / pixel_h
        if ratio < 0.35 or ratio > 2.8:
            continue
        if top < int(height * 0.16) or top > int(height * 0.9):
            continue
        if earliest is None or top < earliest:
            earliest = top
    if earliest is None:
        return None
    return max(24, earliest - step)


def _tesseract_config(tessdata_dir: str | None) -> str:
    """Read the whole page as one text block.

    Tesseract's default layout pass can return only a large heading and drop
    the Negeri, DUN, and candidate lines underneath it.
    """
    parts = ["--oem 1", "--psm 6"]
    if tessdata_dir:
        parts.append(f'--tessdata-dir "{tessdata_dir}"')
    return " ".join(parts)


def prepare_ballot_image(image: QImage, *, stretch: bool = False, smooth: bool = True, deskew: bool = True) -> QImage:
    """Grayscale, straighten a small rotation, and optionally stretch contrast.

    Contrast stretching is for text OCR. Mark detection keeps the original
    stroke darkness so a faint X is not turned into a clear one.
    """
    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    if gray.width() <= 0 or gray.height() <= 0:
        return gray
    gray = _clear_border_dark(gray)
    if deskew:
        angle = _deskew_angle(gray)
        if angle:
            gray = _rotate_on_white(gray, angle)
    if stretch:
        gray = _contrast_stretch(gray)
    short_side = min(gray.width(), gray.height())
    if 0 < short_side < 1400:
        scale = min(3.0, 1400 / short_side)
        gray = gray.scaled(
            max(1, int(gray.width() * scale)),
            max(1, int(gray.height() * scale)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation if smooth else Qt.TransformationMode.FastTransformation,
        )
    return gray


_DESKEW_ANGLES = (-6, -4, -3, -2, -1, 1, 2, 3, 4, 6)


def _deskew_angle(gray: QImage) -> float:
    """Return a small correction, in degrees, when the page is slightly rotated.

    A coarse pass finds the likely angle. A second pass scores that angle and
    its neighbours on a sharper copy, because a heavy downscale can prefer the
    wrong side of the true angle.
    """
    preview = _scaled_for_deskew(gray, 900)
    scores = {angle: _angle_score(preview, angle) for angle in (0, *_DESKEW_ANGLES)}
    best = max(scores, key=scores.get)
    if best == 0 or scores[best] <= scores[0] * 1.08:
        return 0.0
    if preview.width() == gray.width() and preview.height() == gray.height():
        return float(best)
    confirm = {0, best}
    confirm.update(angle for angle in _DESKEW_ANGLES if abs(angle - best) <= 2)
    sharp = _scaled_for_deskew(gray, 1400)
    confirmed = {angle: _angle_score(sharp, angle) for angle in confirm}
    winner = max(confirmed, key=confirmed.get)
    if winner and confirmed[winner] > confirmed.get(0, 0.0) * 1.08:
        return float(winner)
    return 0.0


def _scaled_for_deskew(gray: QImage, limit: int) -> QImage:
    short_side = min(gray.width(), gray.height())
    if short_side <= limit:
        return gray
    scale = limit / short_side
    return gray.scaled(
        max(1, int(gray.width() * scale)),
        max(1, int(gray.height() * scale)),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )


def _angle_score(image: QImage, angle: float) -> float:
    sample = image if angle == 0 else _rotate_on_white(image, angle)
    return _projection_score(_center_crop(sample))


def _clear_border_dark(gray: QImage, threshold: int = 28) -> QImage:
    """Whiten near-black pixels that touch the image edge.

    A rotated photograph leaves black wedges in the corners. Those wedges are
    not ballot ink, and they pull the straightening score off the page.
    """
    raw = bytearray(gray.constBits().tobytes())
    stride = gray.bytesPerLine()
    width = gray.width()
    height = gray.height()
    if width < 3 or height < 3:
        return gray
    seen = bytearray(width * height)
    stack: list[tuple[int, int]] = []

    def consider(x: int, y: int) -> None:
        if x < 0 or y < 0 or x >= width or y >= height:
            return
        index = y * width + x
        if seen[index] or raw[y * stride + x] > threshold:
            return
        seen[index] = 1
        stack.append((x, y))

    for x in range(width):
        consider(x, 0)
        consider(x, height - 1)
    for y in range(height):
        consider(0, y)
        consider(width - 1, y)
    if not stack:
        return gray
    while stack:
        x, y = stack.pop()
        raw[y * stride + x] = 255
        consider(x - 1, y)
        consider(x + 1, y)
        consider(x, y - 1)
        consider(x, y + 1)
    cleaned = QImage(raw, width, height, stride, QImage.Format.Format_Grayscale8)
    return cleaned.copy()


def _center_crop(gray: QImage) -> QImage:
    """Drop the corners so a rotated page's empty wedges do not dominate the score."""
    margin_x = max(0, int(gray.width() * 0.12))
    margin_y = max(0, int(gray.height() * 0.12))
    crop = gray.copy(margin_x, margin_y, max(1, gray.width() - 2 * margin_x), max(1, gray.height() - 2 * margin_y))
    return crop if not crop.isNull() else gray


def _projection_score(gray: QImage) -> float:
    raw = gray.constBits().tobytes()
    stride = gray.bytesPerLine()
    width = gray.width()
    height = gray.height()
    step = 3
    totals: list[int] = []
    for y in range(0, height, step):
        base = y * stride
        dark = 0
        for x in range(0, width, step):
            if raw[base + x] < 90:
                dark += 1
        totals.append(dark)
    if not totals:
        return 0.0
    mean = sum(totals) / len(totals)
    return sum((value - mean) ** 2 for value in totals) / len(totals)


def _rotate_on_white(image: QImage, angle: float) -> QImage:
    source = image.convertToFormat(QImage.Format.Format_ARGB32)
    rotated = source.transformed(QTransform().rotate(angle), Qt.TransformationMode.SmoothTransformation)
    canvas = QImage(rotated.size(), QImage.Format.Format_RGB32)
    canvas.fill(QColor(255, 255, 255))
    painter = QPainter(canvas)
    painter.drawImage(0, 0, rotated)
    painter.end()
    return canvas.convertToFormat(QImage.Format.Format_Grayscale8)


def _contrast_stretch(gray: QImage) -> QImage:
    raw = bytearray(gray.constBits().tobytes())
    stride = gray.bytesPerLine()
    width = gray.width()
    height = gray.height()
    sample = [raw[y * stride + x] for y in range(0, height, 7) for x in range(0, width, 7)]
    if len(sample) < 20:
        return gray
    sample.sort()
    low = sample[int(len(sample) * 0.05)]
    high = sample[int(len(sample) * 0.95)]
    if high - low < 40:
        return gray
    span = high - low
    for index, value in enumerate(raw):
        scaled = int((value - low) * 255 / span)
        raw[index] = min(255, max(0, scaled))
    result = QImage(raw, width, height, stride, QImage.Format.Format_Grayscale8)
    return result.copy()


def _scale_for_text_ocr(gray: QImage) -> QImage:
    """Shrink only the copy Tesseract reads. Mark detection keeps the original file.

    A 4032-wide page makes Tesseract drop the Negeri line. The same page at a
    long side of 1800 still has room for the constituency text.
    """
    long_side = max(gray.width(), gray.height())
    if long_side <= _OCR_LONG_SIDE or long_side <= 0:
        return gray
    scale = _OCR_LONG_SIDE / long_side
    return gray.scaled(
        max(1, int(round(gray.width() * scale))),
        max(1, int(round(gray.height() * scale))),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _write_prepared(image: QImage) -> Path | None:
    """Grayscale, straighten, stretch contrast, and size the copy used for text OCR.

    Small scans are still enlarged. Only a page that was already larger than the
    OCR long-side limit is reduced, so a short wide label is not shrunk again.
    """
    gray = prepare_ballot_image(image, stretch=True)
    if max(image.width(), image.height()) > _OCR_LONG_SIDE:
        gray = _scale_for_text_ocr(gray)
    if gray.width() <= 0 or gray.height() <= 0:
        return None
    handle = tempfile.NamedTemporaryFile(prefix="ballotvision-ocr-", suffix=".png", delete=False)
    handle.close()
    target = Path(handle.name)
    if not gray.save(str(target), "PNG"):
        target.unlink(missing_ok=True)
        return None
    return target


def _is_language_error(message: str) -> bool:
    folded = message.casefold()
    return "failed loading language" in folded or "traineddata" in folded or "error opening data file" in folded


def _is_image_error(message: str) -> bool:
    folded = message.casefold()
    return "pixread" in folded or "error in pix" in folded or "unsupported image" in folded


def _failure(code: str, error: str, thread_id: int) -> OcrResult:
    return OcrResult(
        ok=False,
        text="",
        languages=LANGUAGES,
        mean_confidence=None,
        error=error,
        error_code=code,
        thread_id=thread_id,
    )
