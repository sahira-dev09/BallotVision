"""Officer view of one image: Negeri, DUN, and the marked candidate.

The raw OCR string stays in the stored fields. It is not shown here.
"""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.core.candidates import build_candidate_records
from app.core.constituencies import dun_applicable, find_state
from app.services.location_match import HIGH, NOT_DETECTED
from app.services.mark_recognition import (
    NOT_DETECTED as MARK_NOT_DETECTED,
)
from app.services.mark_recognition import (
    REASON_LOCATION,
    REASON_MULTIPLE,
    REASON_NONE,
    REASON_OCR,
    REASON_OTHER_DUN,
    REASON_OUTSIDE,
    REASON_UNAVAILABLE,
    REASON_UNCLEAR,
    REASON_UNMATCHED,
    STATUS_UNAVAILABLE,
    MarkResult,
    adjudicate,
)
from app.services.ocr_service import BallotReading
from app.widgets.components import StatusBadge

NOT_DETECTED_LABEL = "Not Detected"
_BADGE_TEXT = {
    "High confidence": "High Confidence",
    "Low confidence": "Low Confidence",
    NOT_DETECTED: "Not Detected",
}
_REASON_TEXT = {
    REASON_LOCATION: "Location could not be verified.",
    REASON_OCR: "Location could not be verified.",
    REASON_NONE: "No candidate mark detected.",
    REASON_MULTIPLE: "Multiple candidate marks detected.",
    REASON_UNMATCHED: "Candidate could not be matched to the official candidate list.",
    REASON_OTHER_DUN: "Candidate could not be matched to the official candidate list.",
    REASON_UNCLEAR: "Candidate mark recognition is uncertain.",
    REASON_OUTSIDE: "Candidate mark recognition is uncertain.",
    REASON_UNAVAILABLE: "Candidate mark recognition is uncertain.",
}


def fields_from_reading(reading: BallotReading, *, source_path: str = "") -> dict:
    """Turn one OCR reading into ballot fields. Empty text is not a successful read.

    A Negeri or DUN is stored only when that part of the match is high confidence.
    """
    text = (reading.ocr.text or "").strip() if reading.ocr.ok else ""
    if reading.ocr.ok and text:
        ocr_status = "Read"
        error = ""
        location = reading.location
        match_status = location.status
        match_reason = location.reason
        if location.status == HIGH and location.negeri_status == HIGH:
            negeri = location.negeri or ""
        else:
            negeri = ""
        if location.status == HIGH and location.dun_status == HIGH:
            dun_code = location.dun_code or ""
            dun_name = location.dun_name or ""
        else:
            dun_code = dun_name = ""
    elif reading.ocr.ok:
        ocr_status = "No text"
        error = "No text was extracted."
        match_status = NOT_DETECTED
        match_reason = error
        negeri = dun_code = dun_name = ""
    else:
        ocr_status = "Failed"
        error = reading.ocr.error or "OCR failed."
        match_status = NOT_DETECTED
        match_reason = error
        negeri = dun_code = dun_name = ""
        text = ""
    return {
        "source_path": source_path,
        "ocr_text": text,
        "ocr_status": ocr_status,
        "ocr_error": error,
        "suggested_negeri": negeri,
        "suggested_dun_code": dun_code,
        "suggested_dun_name": dun_name,
        "match_status": match_status,
        "match_reason": match_reason,
        "confirmed_negeri": "",
        "confirmed_dun_code": "",
        "confirmed_dun_name": "",
        "mark_status": "",
        "mark_confidence": "",
        "mark_reason": "",
        "mark_row_text": "",
    }


def fields_from_inspection(reading: BallotReading, mark: MarkResult, *, source_path: str = "") -> dict:
    """Location fields and mark fields stay independent."""
    fields = fields_from_reading(reading, source_path=source_path)
    fields["mark_status"] = mark.status
    fields["mark_confidence"] = mark.confidence
    fields["mark_reason"] = mark.reason
    fields["mark_row_text"] = mark.row_text
    fields["mark_diagnosis"] = mark.diagnosis
    return fields


def officer_view(fields: dict) -> dict:
    """Labels for the panel. A candidate appears only when the marked row matches the DUN list."""
    negeri = (fields.get("suggested_negeri") or "").strip()
    dun = f"{fields.get('suggested_dun_code') or ''} {fields.get('suggested_dun_name') or ''}".strip()
    if fields.get("ocr_status") in {"", "Reading"} or not fields.get("mark_status"):
        return {"negeri": negeri, "dun": dun, "candidate": "", "reason": "", "diagnosis": ""}
    mark = MarkResult(
        status=fields.get("mark_status") or STATUS_UNAVAILABLE,
        confidence=fields.get("mark_confidence") or MARK_NOT_DETECTED,
        row_text=fields.get("mark_row_text") or "",
        box_count=0,
        marked_boxes=1 if fields.get("mark_status") == "single" else 0,
        reason=fields.get("mark_reason") or "",
    )
    state = find_state(negeri) if negeri else None
    official = []
    if negeri and fields.get("suggested_dun_code"):
        official = build_candidate_records(
            state_code=state["code"] if state else "—",
            dun_code=fields.get("suggested_dun_code") or "",
        )
    outcome = adjudicate(
        ocr_ok=fields.get("ocr_status") not in {"", "Failed"},
        location_status=fields.get("match_status") or "",
        negeri=negeri,
        dun_code=fields.get("suggested_dun_code") or "",
        dun_applicable_seat=bool(negeri) and dun_applicable(negeri),
        mark=mark,
        official=official,
    )
    candidate = outcome.candidate_name if outcome.counted else ""
    reason = "" if outcome.counted else _REASON_TEXT.get(outcome.reason, outcome.reason)
    diagnosis = outcome.diagnosis or fields.get("mark_diagnosis") or ""
    return {"negeri": negeri, "dun": dun, "candidate": candidate, "reason": reason, "diagnosis": diagnosis}


class OcrDetailPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.path = ""
        self._fields: dict = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

        negeri_caption = QLabel("Negeri")
        negeri_caption.setObjectName("fieldCaption")
        self.detected_negeri = QLabel(NOT_DETECTED_LABEL)
        self.detected_negeri.setObjectName("detectedNegeri")
        self.detected_negeri.setWordWrap(True)
        dun_caption = QLabel("DUN")
        dun_caption.setObjectName("fieldCaption")
        self.detected_dun = QLabel(NOT_DETECTED_LABEL)
        self.detected_dun.setObjectName("detectedDun")
        self.detected_dun.setWordWrap(True)
        candidate_caption = QLabel("Candidate")
        candidate_caption.setObjectName("fieldCaption")
        self.detected_candidate = QLabel(NOT_DETECTED_LABEL)
        self.detected_candidate.setObjectName("detectedCandidate")
        self.detected_candidate.setWordWrap(True)
        self.detection_reason = QLabel("")
        self.detection_reason.setObjectName("detectionReason")
        self.detection_reason.setWordWrap(True)
        self.detection_diagnosis = QLabel("")
        self.detection_diagnosis.setObjectName("detectionDiagnosis")
        self.detection_diagnosis.setWordWrap(True)
        layout.addWidget(negeri_caption)
        layout.addWidget(self.detected_negeri)
        layout.addWidget(dun_caption)
        layout.addWidget(self.detected_dun)
        layout.addWidget(candidate_caption)
        layout.addWidget(self.detected_candidate)
        layout.addWidget(self.detection_reason)
        layout.addWidget(self.detection_diagnosis)

        location_caption = QLabel("Location confidence")
        location_caption.setObjectName("fieldCaption")
        self.match_badge = StatusBadge("Not Detected", "neutral")
        self.match_badge.setObjectName("ocrMatch")
        mark_caption = QLabel("Candidate mark confidence")
        mark_caption.setObjectName("fieldCaption")
        self.mark_badge = StatusBadge("Not Detected", "neutral")
        self.mark_badge.setObjectName("markConfidence")
        layout.addWidget(location_caption)
        layout.addWidget(self.match_badge, 0)
        layout.addWidget(mark_caption)
        layout.addWidget(self.mark_badge, 0)

    def load(self, path: str, fields: dict) -> None:
        self.path = path
        self._fields = dict(fields)
        self._show_match(fields)

    def apply_reading(self, path: str, reading: BallotReading) -> dict:
        fields = fields_from_reading(reading, source_path=path)
        if path == self.path:
            self.load(path, fields)
        return fields

    def apply_inspection(self, path: str, reading: BallotReading, mark: MarkResult) -> dict:
        fields = fields_from_inspection(reading, mark, source_path=path)
        if path == self.path:
            self.load(path, fields)
        return fields

    def snapshot(self) -> dict:
        fields = dict(self._fields)
        fields["source_path"] = self.path
        return fields

    def _show_match(self, fields: dict) -> None:
        status = fields.get("match_status") or NOT_DETECTED
        kind = {"High confidence": "success", "Low confidence": "warning"}.get(status, "neutral")
        self.match_badge.set_kind(kind, _BADGE_TEXT.get(status, "Not Detected"))
        view = officer_view(fields)
        self.detected_negeri.setText(view["negeri"] or NOT_DETECTED_LABEL)
        self.detected_dun.setText(view["dun"] or NOT_DETECTED_LABEL)
        self.detected_candidate.setText(view["candidate"] or NOT_DETECTED_LABEL)
        self.detection_reason.setText(view["reason"])
        self.detection_diagnosis.setText(view.get("diagnosis") or "")
        mark_status = fields.get("mark_confidence") or MARK_NOT_DETECTED
        mark_kind = {"High confidence": "success", "Low confidence": "warning"}.get(mark_status, "neutral")
        self.mark_badge.set_kind(mark_kind, _BADGE_TEXT.get(mark_status, "Not Detected"))
