"""Find X marks inside candidate voting boxes.

The selected row is the box that contains the mark. A candidate name read from
the page is never treated as a vote by itself. Name text is used only to match
an already marked row to the official list.
"""

from __future__ import annotations

import math
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QRect
from PySide6.QtGui import QImage

from app.services.location_match import HIGH
from app.services.ocr_service import (
    _clear_border_dark,
    _deskew_angle,
    _rotate_on_white,
    _seconds_left,
    _tesseract_config,
    prepare_ballot_image,
    resolve_tesseract_cmd,
)

HIGH_CONFIDENCE = "High confidence"
LOW_CONFIDENCE = "Low confidence"
NOT_DETECTED = "Not detected"

STATUS_SINGLE = "single"
STATUS_NONE = "none"
STATUS_MULTIPLE = "multiple"
STATUS_UNCLEAR = "unclear"
STATUS_OUTSIDE = "outside"
STATUS_UNAVAILABLE = "unavailable"

REASON_NONE = "No candidate mark detected."
REASON_MULTIPLE = "Multiple candidate marks detected."
REASON_UNCLEAR = "Candidate mark is unclear."
REASON_OUTSIDE = "Candidate mark is outside the voting box."
REASON_UNMATCHED = "The marked candidate is not on the official list for this DUN."
REASON_OTHER_DUN = "The marked candidate is registered for a different constituency."
REASON_LOCATION = "Location could not be verified."
REASON_OCR = "OCR processing failed."
REASON_UNAVAILABLE = "Candidate mark recognition could not read this image."


@dataclass(frozen=True)
class MarkResult:
    status: str
    confidence: str
    row_text: str
    box_count: int
    marked_boxes: int
    reason: str
    diagnosis: str = ""


@dataclass(frozen=True)
class BallotAdjudication:
    counted: bool
    review: bool
    reason: str
    candidate_id: str
    candidate_name: str
    location_confidence: str
    mark_confidence: str
    diagnosis: str = ""


DIAG_BOX = "Voting box detection: no box border was found."
DIAG_X_NONE = "X-mark detection: voting boxes were found, and no X was inside them."
DIAG_X_UNCLEAR = "X-mark detection: a mark is inside a box, but it is not a clear X."
DIAG_X_OUTSIDE = "X-mark detection: an X was found outside the voting boxes."
DIAG_X_MULTI = "X-mark detection: more than one voting box contains a mark."
DIAG_NAME = "Candidate name extraction: the name beside the marked box could not be read."
DIAG_NAME_OK = "Candidate name extraction: the name was read from the marked row."


def recognize_marks(image_path: str, deadline: float | None = None) -> MarkResult:
    """Detect voting boxes and X marks. Does not choose a candidate by name."""
    if deadline is not None and _seconds_left(deadline, 60) < 1:
        return MarkResult(
            STATUS_UNAVAILABLE,
            NOT_DETECTED,
            "",
            0,
            0,
            REASON_UNAVAILABLE,
            "Inspection timed out before mark detection.",
        )
    image = QImage(image_path)
    if image.isNull():
        return MarkResult(STATUS_UNAVAILABLE, NOT_DETECTED, "", 0, 0, REASON_UNAVAILABLE, "The image could not be opened.")
    gray = image.convertToFormat(QImage.Format.Format_Grayscale8)
    angle = _deskew_angle(_clear_border_dark(gray))
    if angle:
        gray = _rotate_on_white(gray, angle)
    boxes = _voting_boxes(gray)
    clear: list[QRect] = []
    faint: list[QRect] = []
    for box in boxes:
        kind = _mark_in_box(gray, box)
        if kind == "clear":
            clear.append(box)
        elif kind in {"faint", "partial"}:
            faint.append(box)
    outside = _outside_mark(gray, boxes)
    if len(clear) > 1 or (len(clear) == 1 and faint):
        return MarkResult(
            STATUS_MULTIPLE, LOW_CONFIDENCE, "", len(boxes), len(clear) + len(faint), REASON_MULTIPLE, DIAG_X_MULTI
        )
    if len(clear) == 1 and not faint:
        row_text = _row_text(gray, clear[0], deadline)
        diagnosis = DIAG_NAME_OK if row_text else DIAG_NAME
        return MarkResult(STATUS_SINGLE, HIGH_CONFIDENCE, row_text, len(boxes), 1, "", diagnosis)
    if faint:
        return MarkResult(STATUS_UNCLEAR, LOW_CONFIDENCE, "", len(boxes), len(faint), REASON_UNCLEAR, DIAG_X_UNCLEAR)
    if outside:
        diagnosis = DIAG_X_OUTSIDE if boxes else DIAG_BOX
        return MarkResult(STATUS_OUTSIDE, LOW_CONFIDENCE, "", len(boxes), 0, REASON_OUTSIDE, diagnosis)
    if not boxes:
        return MarkResult(STATUS_NONE, NOT_DETECTED, "", 0, 0, REASON_NONE, DIAG_BOX)
    return MarkResult(STATUS_NONE, NOT_DETECTED, "", len(boxes), 0, REASON_NONE, DIAG_X_NONE)


def adjudicate(
    *,
    ocr_ok: bool,
    location_status: str,
    negeri: str,
    dun_code: str,
    dun_applicable_seat: bool,
    mark: MarkResult,
    official: list[dict],
) -> BallotAdjudication:
    """Apply the counting rules. High location confidence does not cast a vote."""
    location_confidence = location_status or NOT_DETECTED
    if not ocr_ok:
        return _review(REASON_OCR, location_confidence, NOT_DETECTED, "Location matching: OCR did not return text.")
    location_ready = (
        location_status == HIGH
        and bool(negeri)
        and (bool(dun_code) if dun_applicable_seat else False)
    )
    if not location_ready:
        return _review(
            REASON_LOCATION,
            location_confidence,
            mark.confidence,
            "Location matching: the Negeri and DUN reading was not reliable.",
        )
    if mark.status == STATUS_UNAVAILABLE:
        return _review(REASON_UNAVAILABLE, location_confidence, mark.confidence, mark.diagnosis)
    if mark.status != STATUS_SINGLE or mark.confidence != HIGH_CONFIDENCE:
        return _review(mark.reason or REASON_UNCLEAR, location_confidence, mark.confidence, mark.diagnosis)
    matched = _official_hit(mark.row_text, official, dun_code)
    if matched is None:
        other = _name_on_other_dun(mark.row_text, official, dun_code)
        reason = REASON_OTHER_DUN if other else REASON_UNMATCHED
        stage = "Candidate matching: the marked row is not an official candidate for this DUN."
        if not (mark.row_text or "").strip():
            stage = mark.diagnosis or DIAG_NAME
        return _review(reason, location_confidence, mark.confidence, stage)
    return BallotAdjudication(
        counted=True,
        review=False,
        reason="",
        candidate_id=str(matched.get("candidate_id") or ""),
        candidate_name=str(matched.get("candidate_name") or matched.get("name") or ""),
        location_confidence=location_confidence,
        mark_confidence=mark.confidence,
        diagnosis=mark.diagnosis,
    )


def _review(reason: str, location_confidence: str, mark_confidence: str, diagnosis: str = "") -> BallotAdjudication:
    return BallotAdjudication(
        counted=False,
        review=True,
        reason=reason,
        candidate_id="",
        candidate_name="",
        location_confidence=location_confidence,
        mark_confidence=mark_confidence,
        diagnosis=diagnosis,
    )


def _official_hit(row_text: str, official: list[dict], dun_code: str) -> dict | None:
    records = []
    names = []
    for record in official:
        if dun_code and record.get("dun_code") not in {None, "", dun_code}:
            continue
        name = (record.get("candidate_name") or record.get("name") or "").strip()
        if not name:
            continue
        names.append(name)
        records.append(record)
    found = _phrases_in_text(row_text, names)
    if len(found) != 1:
        return None
    hits = [record for record in records if (record.get("candidate_name") or record.get("name")) == found[0]]
    if len(hits) != 1:
        return None
    return hits[0]


def _name_on_other_dun(row_text: str, official: list[dict], dun_code: str) -> bool:
    """True when the row names a listed person whose record is for another DUN."""
    if not dun_code:
        return False
    other_names = []
    for record in official:
        if record.get("dun_code") in {None, "", dun_code}:
            continue
        name = (record.get("candidate_name") or record.get("name") or "").strip()
        if name:
            other_names.append(name)
    if not other_names:
        return False
    return len(_phrases_in_text(row_text, other_names)) == 1


def _phrases_in_text(text: str, names: list[str]) -> list[str]:
    folded = (text or "").casefold()
    found: list[str] = []
    for name in names:
        parts = [part for part in name.casefold().split() if part]
        if not parts:
            continue
        pattern = r"(?<![a-z0-9])" + r"\s+".join(re.escape(part) for part in parts) + r"(?![a-z0-9])"
        if re.search(pattern, folded) and name not in found:
            found.append(name)
    return found


def _voting_boxes(gray: QImage) -> list[QRect]:
    components = _components(gray, threshold=72)
    width = gray.width()
    height = gray.height()
    minimum = max(18, int(min(width, height) * 0.04))
    boxes: list[QRect] = []
    for item in components:
        rect: QRect = item["rect"]
        if rect.width() < minimum or rect.height() < minimum:
            continue
        ratio = rect.width() / rect.height()
        if ratio < 0.6 or ratio > 1.6:
            continue
        if rect.top() < int(height * 0.12):
            continue
        fill = item["count"] / max(1, (rect.width() * rect.height()) / (item["step"] ** 2))
        if fill > 0.45:
            continue
        if _perimeter_dark(gray, rect, item["step"]) < 0.55:
            continue
        boxes.append(rect)
    for rect in _frame_boxes(gray, minimum):
        boxes.append(rect)
    boxes.sort(key=lambda rect: (rect.top(), rect.left()))
    kept: list[QRect] = []
    for rect in boxes:
        if any(_same_box(rect, previous) for previous in kept):
            continue
        kept.append(rect)
    return kept


def _frame_boxes(gray: QImage, minimum: int) -> list[QRect]:
    """Pair top and bottom strokes when touching boxes have merged into one component.

    A pair is kept only when both sides are continuous and the outline is nearly square.
    Lengths are fractions of the page, not a fixed pixel size.
    """
    raw, stride = _bytes(gray)
    width = gray.width()
    height = gray.height()
    step = 2
    cols = (width + step - 1) // step
    rows = (height + step - 1) // step
    dark = bytearray(cols * rows)
    for row in range(rows):
        y = min(height - 1, row * step)
        base = y * stride
        for col in range(cols):
            if raw[base + min(width - 1, col * step)] < 72:
                dark[row * cols + col] = 1
    solid = _solid_cells(dark, cols, rows)
    maximum = int(min(width, height) * 0.4)
    segments: list[tuple[int, int, int]] = []
    active: list[list[int]] = []
    for row in range(rows):
        runs: list[tuple[int, int]] = []
        col = 0
        base = row * cols
        while col < cols:
            if not dark[base + col] or solid[base + col]:
                col += 1
                continue
            start = col
            while col < cols and dark[base + col] and not solid[base + col]:
                col += 1
            length = (col - start) * step
            if minimum <= length <= maximum:
                runs.append((start, col - 1))
        continued: list[list[int]] = []
        taken: set[int] = set()
        for start, end in runs:
            match = None
            for index, segment in enumerate(active):
                if index in taken:
                    continue
                if row - segment[3] <= 2 and abs(segment[0] - start) <= 2 and abs(segment[1] - end) <= 2:
                    match = segment
                    taken.add(index)
                    break
            if match is None:
                continued.append([start, end, row, row])
                continue
            match[0] = min(match[0], start)
            match[1] = max(match[1], end)
            match[3] = row
            continued.append(match)
        for index, segment in enumerate(active):
            if index in taken:
                continue
            thickness = (segment[3] - segment[2] + 1) * step
            length = (segment[1] - segment[0] + 1) * step
            if thickness <= max(step * 4, int(length * 0.15)):
                segments.append((segment[2], segment[0], segment[1]))
        active = continued
    for segment in active:
        thickness = (segment[3] - segment[2] + 1) * step
        length = (segment[1] - segment[0] + 1) * step
        if thickness <= max(step * 4, int(length * 0.15)):
            segments.append((segment[2], segment[0], segment[1]))
    segments.sort(key=lambda item: (item[0], item[1]))
    found: list[QRect] = []
    header = int(height * 0.12)
    for index, (top_y, top_start, top_end) in enumerate(segments):
        if top_y * step < header:
            continue
        length = (top_end - top_start + 1) * step
        best: QRect | None = None
        best_delta = length
        for bottom_y, bottom_start, bottom_end in segments[index + 1 :]:
            dy = (bottom_y - top_y) * step
            if dy > int(length * 1.12):
                break
            if dy < int(length * 0.88):
                continue
            bottom_length = (bottom_end - bottom_start + 1) * step
            if abs(length - bottom_length) > length * 0.12:
                continue
            slack = max(2, int(length * 0.04 / step))
            if abs(top_start - bottom_start) > slack or abs(top_end - bottom_end) > slack:
                continue
            if _span_dark(dark, cols, rows, top_start, top_y, bottom_y, solid) < 0.82:
                continue
            if _span_dark(dark, cols, rows, top_end, top_y, bottom_y, solid) < 0.82:
                continue
            if _interior_fill(dark, cols, top_start, top_end, top_y, bottom_y) > 0.45:
                continue
            delta = abs(dy - length)
            if delta < best_delta:
                best_delta = delta
                best = QRect(
                    top_start * step,
                    top_y * step,
                    max(1, (top_end - top_start) * step + 1),
                    max(1, dy + 1),
                )
        if best is not None:
            found.append(best)
    return found


def _solid_cells(dark: bytearray, cols: int, rows: int) -> bytearray:
    """Mark cells that sit inside a dark mass, such as a photographed page border.

    A voting-box stroke is only a few cells thick, so the samples beside it stay light and it is not marked.
    """
    solid = bytearray(cols * rows)
    probes = ((8, 0), (-8, 0), (0, 8), (0, -8), (6, 6), (-6, 6), (6, -6), (-6, -6))
    for y in range(rows):
        base = y * cols
        for x in range(cols):
            if not dark[base + x]:
                continue
            hits = 0
            for dx, dy in probes:
                xx = x + dx
                yy = y + dy
                if xx < 0 or yy < 0 or xx >= cols or yy >= rows or dark[yy * cols + xx]:
                    hits += 1
            if hits >= 6:
                solid[base + x] = 1
    return solid


def _span_dark(
    dark: bytearray,
    cols: int,
    rows: int,
    x: int,
    y0: int,
    y1: int,
    solid: bytearray | None = None,
) -> float:
    total = 0
    hits = 0
    for y in range(max(0, y0), min(rows - 1, y1) + 1):
        total += 1
        found = False
        for offset in range(-3, 4):
            xx = x + offset
            if xx < 0 or xx >= cols:
                continue
            index = y * cols + xx
            if dark[index] or (solid is not None and solid[index]):
                found = True
                break
        if found:
            hits += 1
    if total == 0:
        return 0.0
    return hits / total


def _interior_fill(dark: bytearray, cols: int, x0: int, x1: int, y0: int, y1: int) -> float:
    inset = 2
    left = x0 + inset
    right = x1 - inset
    top = y0 + inset
    bottom = y1 - inset
    if right <= left or bottom <= top:
        return 1.0
    total = 0
    hits = 0
    for y in range(top, bottom + 1):
        base = y * cols
        for x in range(left, right + 1):
            total += 1
            if dark[base + x]:
                hits += 1
    if total == 0:
        return 1.0
    return hits / total


def _perimeter_dark(gray: QImage, rect: QRect, step: int = 1) -> float:
    """Look a short distance inside the bounds so the stroke is scored, not the white pixel beside it.

    The search depth follows the box size and the sampling step. It is not a fixed border thickness.
    """
    raw, stride = _bytes(gray)
    width = gray.width()
    height = gray.height()
    band = max(step, int(min(rect.width(), rect.height()) * 0.03))
    samples = 0
    hits = 0
    for index in range(40):
        frac = index / 39
        edges = (
            (rect.left() + int(frac * max(0, rect.width() - 1)), rect.top(), 0, 1),
            (rect.left() + int(frac * max(0, rect.width() - 1)), rect.bottom(), 0, -1),
            (rect.left(), rect.top() + int(frac * max(0, rect.height() - 1)), 1, 0),
            (rect.right(), rect.top() + int(frac * max(0, rect.height() - 1)), -1, 0),
        )
        for x, y, dx, dy in edges:
            samples += 1
            found = False
            for offset in range(band + 1):
                if _dark(raw, stride, width, height, x + dx * offset, y + dy * offset, 80):
                    found = True
                    break
            if found:
                hits += 1
    if samples == 0:
        return 0.0
    return hits / samples


def _same_box(left: QRect, right: QRect) -> bool:
    limit = 0.2 * min(left.width(), left.height(), right.width(), right.height())
    return (
        left.intersects(right)
        and abs(left.center().x() - right.center().x()) < limit
        and abs(left.center().y() - right.center().y()) < limit
    )


def _mark_in_box(gray: QImage, box: QRect) -> str:
    strict = _diagonal_score(gray, _inset(box, 0.18), 70)
    loose = _diagonal_score(gray, _inset(box, 0.18), 175)
    if _is_clear(strict):
        return "clear"
    if _is_clear(loose) and not _is_clear(strict):
        return "faint"
    if _is_partial(strict) or _is_partial(loose):
        return "partial"
    return "none"


def _outside_mark(gray: QImage, boxes: list[QRect]) -> bool:
    for item in _components(gray, threshold=70):
        rect: QRect = item["rect"]
        if rect.width() < 24 or rect.height() < 24:
            continue
        ratio = rect.width() / max(1, rect.height())
        if ratio < 0.45 or ratio > 2.2:
            continue
        center = rect.center()
        if any(box.contains(center) for box in boxes):
            continue
        if boxes:
            typical = sorted(box.width() for box in boxes)[len(boxes) // 2]
            if rect.width() < typical * 0.45 or rect.height() < typical * 0.45:
                continue
        else:
            short_side = min(gray.width(), gray.height())
            if rect.width() < short_side * 0.04 or rect.height() < short_side * 0.04:
                continue
        if _is_clear(_axis_score(gray, _inset(rect, 0.08), 70)):
            return True
    return False


def _is_clear(score: tuple[float, float, float]) -> bool:
    main, anti, midline = score
    return main >= 0.42 and anti >= 0.42 and midline <= 0.72


def _is_partial(score: tuple[float, float, float]) -> bool:
    main, anti, _midline = score
    strong = (main >= 0.42) ^ (anti >= 0.42)
    return strong and max(main, anti) >= 0.42 and min(main, anti) < 0.28


def _inset(rect: QRect, fraction: float) -> QRect:
    dx = max(2, int(rect.width() * fraction))
    dy = max(2, int(rect.height() * fraction))
    inner = rect.adjusted(dx, dy, -dx, -dy)
    if inner.width() < 6 or inner.height() < 6:
        return rect
    return inner


def _axis_score(gray: QImage, rect: QRect, threshold: int) -> tuple[float, float, float]:
    """Upright X only. Used outside boxes so letter shapes are not called an X."""
    main = _line_coverage(gray, rect, 45, threshold, radius=0)
    anti = _line_coverage(gray, rect, 135, threshold, radius=0)
    mid = _line_coverage(gray, rect, 0, threshold, along_width=True, radius=0)
    return main, anti, mid


def _diagonal_score(gray: QImage, rect: QRect, threshold: int) -> tuple[float, float, float]:
    """Score both strokes, allowing a small tilt. The coverage bar stays the same.

    The horizontal check stays on a single pixel row. A thick stroke is not
    treated as a filled box just because nearby pixels are dark.
    """
    best = (0.0, 0.0, 1.0)
    for tilt in range(-18, 19, 6):
        main = _line_coverage(gray, rect, 45 + tilt, threshold, radius=2)
        anti = _line_coverage(gray, rect, 135 + tilt, threshold, radius=2)
        mid = _line_coverage(gray, rect, 0, threshold, along_width=True, radius=0)
        if min(main, anti) > min(best[0], best[1]):
            best = (main, anti, mid)
    return best


def _line_coverage(
    gray: QImage,
    rect: QRect,
    angle: float,
    threshold: int,
    *,
    along_width: bool = False,
    radius: int = 1,
) -> float:
    raw, stride = _bytes(gray)
    width = gray.width()
    height = gray.height()
    center_x = rect.left() + rect.width() / 2
    center_y = rect.top() + rect.height() / 2
    length = rect.width() * 0.72 if along_width else min(rect.width(), rect.height()) * 0.72
    radians = math.radians(angle)
    direction_x = math.cos(radians)
    direction_y = math.sin(radians)
    samples = 36
    hits = 0
    for index in range(samples):
        offset = (index / (samples - 1) - 0.5) * length
        base_x = center_x + direction_x * offset
        base_y = center_y + direction_y * offset
        found = False
        for side in range(-radius, radius + 1):
            x = int(base_x - direction_y * side)
            y = int(base_y + direction_x * side)
            if _dark(raw, stride, width, height, x, y, threshold):
                found = True
                break
        if found:
            hits += 1
    return hits / samples


def _components(gray: QImage, threshold: int) -> list[dict]:
    raw, stride = _bytes(gray)
    width = gray.width()
    height = gray.height()
    step = 2
    cols = (width + step - 1) // step
    rows = (height + step - 1) // step
    dark = bytearray(cols * rows)
    for row in range(rows):
        y = min(height - 1, row * step)
        base = y * stride
        for col in range(cols):
            x = min(width - 1, col * step)
            if raw[base + x] < threshold:
                dark[row * cols + col] = 1
    seen = bytearray(cols * rows)
    found: list[dict] = []
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
            min_x = min(min_x, cx)
            max_x = max(max_x, cx)
            min_y = min(min_y, cy)
            max_y = max(max_y, cy)
            for nxt, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if nxt < 0 or ny < 0 or nxt >= cols or ny >= rows:
                    continue
                index = ny * cols + nxt
                if dark[index] and not seen[index]:
                    seen[index] = 1
                    stack.append(index)
        if count < 12:
            continue
        rect = QRect(
            min_x * step,
            min_y * step,
            max(1, (max_x - min_x) * step + 1),
            max(1, (max_y - min_y) * step + 1),
        )
        found.append({"rect": rect, "count": count, "step": step})
    return found


def _row_text(image: QImage, box: QRect, deadline: float | None = None) -> str:
    command = resolve_tesseract_cmd()
    if command is None or image.isNull():
        return ""
    strip = QRect(box.right() + 6, max(0, box.top() - 6), max(80, image.width() - box.right() - 12), box.height() + 12)
    strip = strip.intersected(QRect(0, 0, image.width(), image.height()))
    if strip.width() < 20 or strip.height() < 16:
        return ""
    crop = prepare_ballot_image(image.copy(strip), stretch=True, smooth=True, deskew=False)
    handle = tempfile.NamedTemporaryFile(prefix="ballotvision-row-", suffix=".png", delete=False)
    handle.close()
    target = Path(handle.name)
    try:
        if not crop.save(str(target), "PNG"):
            return ""
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = command
        timeout = 8 if deadline is None else _seconds_left(deadline, 8)
        if timeout < 1:
            return ""
        text = pytesseract.image_to_string(str(target), lang="eng+msa", config="--oem 1 --psm 7", timeout=timeout)
        fallback = 0 if deadline is None else _seconds_left(deadline, 6)
        if len((text or "").split()) < 2 and (deadline is None or fallback >= 1):
            alt = pytesseract.image_to_string(
                str(target),
                lang="eng+msa",
                config=_tesseract_config(None),
                timeout=6 if deadline is None else fallback,
            )
            if len((alt or "").split()) > len((text or "").split()):
                text = alt
    except Exception:
        return ""
    finally:
        target.unlink(missing_ok=True)
    return " ".join((text or "").split())


def _bytes(gray: QImage) -> tuple[bytes, int]:
    return gray.constBits().tobytes(), gray.bytesPerLine()


def _dark(raw: bytes, stride: int, width: int, height: int, x: int, y: int, threshold: int) -> bool:
    if x < 0 or y < 0 or x >= width or y >= height:
        return False
    return raw[y * stride + x] < threshold
