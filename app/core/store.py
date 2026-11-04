"""
In-memory demonstration data for the UI prototype.

Nothing here is a real election result or an AI prediction.
Pages share one Store so a review or export can update other screens.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.core.candidates import DEMO_VOTE_COUNTS, apply_result_status, build_candidate_records
from app.core.constituencies import default_location, dun_applicable, find_state, location_key
from app.core.constants import (
    CANDIDATES,
    DEFAULT_SETTINGS,
    DEMO_BATCH_ID,
    DEMO_ELECTION_NAME,
)
from app.core.utils import settings_path

DEMO_STATE, DEMO_DUN_CODE, DEMO_DUN_NAME = default_location()
DEMO_LOCATION_KEY = location_key(DEMO_STATE, DEMO_DUN_CODE)


def empty_session(kind: str = "none") -> dict:
    hours = ("08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00")
    return {
        "kind": kind,
        "stats": {
            "total_processed": 0,
            "valid": 0,
            "flagged": 0,
            "accuracy": 0.0,
            "rejected": 0,
            "pending_reviews": 0,
        },
        "candidates": build_candidate_records(state_code="—", dun_code="—"),
        "classification": {"valid": 0, "rejected": 0, "needs_review": 0},
        "activity": [(hour, 0) for hour in hours],
        "batches": [],
        "processing_events": [],
        "flagged": [],
        "imported": [],
    }


def _dt(days_ago: int, hour: int, minute: int) -> datetime:
    base = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    return base - timedelta(days=days_ago)


def build_sample_data() -> dict:
    """Factory values used on first launch and after Clear Demo Data."""
    flagged = [
        {
            "id": "BLT-2041",
            "batch": "BATCH-18",
            "reason": "Faint mark near box edge",
            "confidence": 71,
            "status": "Pending Review",
            "detected": "Rizal Purnama",
            "notes": "",
        },
        {
            "id": "BLT-2048",
            "batch": "BATCH-18",
            "reason": "Possible double mark",
            "confidence": 64,
            "status": "Pending Review",
            "detected": "Amalia Suria",
            "notes": "",
            "location_key": DEMO_LOCATION_KEY,
            "data_kind": "prototype_demo",
        },
        {
            "id": "BLT-2055",
            "batch": "BATCH-19",
            "reason": "Low contrast scan",
            "confidence": 69,
            "status": "Pending Review",
            "detected": "Nora Bentara",
            "notes": "",
            "location_key": DEMO_LOCATION_KEY,
            "data_kind": "prototype_demo",
        },
        {
            "id": "BLT-2062",
            "batch": "BATCH-19",
            "reason": "Mark outside designated box",
            "confidence": 73,
            "status": "Pending Review",
            "detected": "Amalia Suria",
            "notes": "",
            "location_key": DEMO_LOCATION_KEY,
            "data_kind": "prototype_demo",
        },
        {
            "id": "BLT-2070",
            "batch": "BATCH-20",
            "reason": "Ambiguous stroke direction",
            "confidence": 66,
            "status": "Pending Review",
            "detected": "Faizal Ombak",
            "notes": "",
            "location_key": DEMO_LOCATION_KEY,
            "data_kind": "prototype_demo",
        },
        {
            "id": "BLT-2077",
            "batch": "BATCH-20",
            "reason": "Fold line across candidate row",
            "confidence": 62,
            "status": "Pending Review",
            "detected": "Rizal Purnama",
            "notes": "",
        },
        {
            "id": "BLT-1988",
            "batch": "BATCH-17",
            "reason": "Smudge near Nora Bentara",
            "confidence": 74,
            "status": "Reviewed",
            "detected": "Nora Bentara",
            "decision": "Confirm Detected Mark",
            "notes": "Officer confirmed intended mark.",
            "location_key": DEMO_LOCATION_KEY,
            "data_kind": "prototype_demo",
        },
        {
            "id": "BLT-1994",
            "batch": "BATCH-17",
            "reason": "Overvote suspected",
            "confidence": 58,
            "status": "Reviewed",
            "detected": "Amalia Suria",
            "decision": "Mark as Rejected",
            "notes": "Two marks of similar density.",
            "location_key": DEMO_LOCATION_KEY,
            "data_kind": "prototype_demo",
        },
    ]

    audit = [
        {
            "id": "AUD-1001",
            "time": _dt(2, 9, 12),
            "user": "Sahira",
            "action": "Imported ballot images",
            "related": "BATCH-17",
            "type": "Image Import",
            "status": "Completed",
            "detail": "120 PNG files imported for demonstration batch 17.",
        },
        {
            "id": "AUD-1002",
            "time": _dt(2, 9, 18),
            "user": "System",
            "action": "Started processing simulation",
            "related": "BATCH-17",
            "type": "Processing Simulation",
            "status": "Completed",
            "detail": "Simulated classification only. No AI model was used.",
        },
        {
            "id": "AUD-1003",
            "time": _dt(2, 9, 41),
            "user": "System",
            "action": "Flagged ballots for review",
            "related": "BATCH-17",
            "type": "Flagged Ballot",
            "status": "Completed",
            "detail": "8 sample ballots placed in the review queue.",
        },
        {
            "id": "AUD-1004",
            "time": _dt(1, 14, 5),
            "user": "Sahira",
            "action": "Confirmed detected mark",
            "related": "BLT-1988",
            "type": "Review Decision",
            "status": "Completed",
            "detail": "Decision: Confirm Detected Mark for Nora Bentara.",
        },
        {
            "id": "AUD-1005",
            "time": _dt(1, 14, 11),
            "user": "Sahira",
            "action": "Rejected ballot",
            "related": "BLT-1994",
            "type": "Review Decision",
            "status": "Completed",
            "detail": "Decision: Mark as Rejected due to suspected overvote.",
        },
        {
            "id": "AUD-1006",
            "time": _dt(1, 16, 22),
            "user": "Sahira",
            "action": "Imported ballot images",
            "related": "BATCH-18",
            "type": "Image Import",
            "status": "Completed",
            "detail": "86 JPG files imported for demonstration batch 18.",
        },
        {
            "id": "AUD-1007",
            "time": _dt(0, 10, 4),
            "user": "System",
            "action": "Started processing simulation",
            "related": "BATCH-20",
            "type": "Processing Simulation",
            "status": "Completed",
            "detail": "Demo processing mode was enabled.",
        },
        {
            "id": "AUD-1008",
            "time": _dt(0, 11, 30),
            "user": "Sahira",
            "action": "Exported results CSV",
            "related": "RESULTS",
            "type": "CSV Export",
            "status": "Completed",
            "detail": "Simulated results exported. File is not an official return.",
        },
        {
            "id": "AUD-1009",
            "time": _dt(0, 8, 2),
            "user": "System",
            "action": "Recognition engine check",
            "related": "SYSTEM",
            "type": "System Event",
            "status": "Warning",
            "detail": "Recognition engine is not connected in this prototype.",
        },
    ]

    for item in flagged:
        item["location_key"] = DEMO_LOCATION_KEY
        item["data_kind"] = "prototype_demo"

    demo_session = empty_session("prototype_demo")
    demo_session.update(
        {
            "stats": {
                "total_processed": 2450,
                "valid": 2391,
                "flagged": 42,
                "accuracy": 98.4,
                "rejected": 17,
                "pending_reviews": 42,
            },
            "candidates": build_candidate_records(
                state_code="JHR",
                dun_code=DEMO_DUN_CODE,
                votes=DEMO_VOTE_COUNTS,
                dataset_type="simulated",
            ),
            "classification": {"valid": 2391, "rejected": 17, "needs_review": 42},
            "activity": [
                ("08:00", 180),
                ("09:00", 310),
                ("10:00", 420),
                ("11:00", 390),
                ("12:00", 210),
                ("13:00", 350),
                ("14:00", 410),
                ("15:00", 180),
            ],
            "batches": [
                {"id": DEMO_BATCH_ID, "time": "Today, 10:04", "images": 94, "valid": 88, "flagged": 5, "status": "Completed"},
                {"id": "BATCH-019", "time": "Today, 09:12", "images": 110, "valid": 104, "flagged": 4, "status": "Completed"},
                {"id": "BATCH-018", "time": "Yesterday, 16:22", "images": 86, "valid": 81, "flagged": 4, "status": "Completed"},
                {"id": "BATCH-017", "time": "Yesterday, 09:18", "images": 120, "valid": 116, "flagged": 3, "status": "Reviewed"},
                {"id": "BATCH-016", "time": "13 Oct 2026", "images": 102, "valid": 99, "flagged": 2, "status": "Completed"},
            ],
            "processing_events": [
                {
                    "time": "10:18",
                    "description": "Batch summary generated for officer briefing",
                    "batch": DEMO_BATCH_ID,
                    "status": "Completed",
                },
                {
                    "time": "10:12",
                    "description": "Officer review completed for two sample ballots",
                    "batch": "BATCH-017",
                    "status": "Completed",
                },
                {
                    "time": "10:08",
                    "description": "Unclear ballots flagged for officer verification",
                    "batch": DEMO_BATCH_ID,
                    "status": "Needs Review",
                },
                {
                    "time": "10:06",
                    "description": "Demonstration rules applied — not AI classification",
                    "batch": DEMO_BATCH_ID,
                    "status": "Completed",
                },
                {
                    "time": "10:05",
                    "description": "Image processing completed for the imported sample set",
                    "batch": DEMO_BATCH_ID,
                    "status": "Completed",
                },
                {
                    "time": "10:04",
                    "description": "Sample batch imported for this demonstration",
                    "batch": DEMO_BATCH_ID,
                    "status": "Completed",
                },
            ],
            "flagged": flagged,
            "imported": [],
        }
    )

    return {
        "location_sessions": {DEMO_LOCATION_KEY: demo_session} if DEMO_LOCATION_KEY else {},
        "stats": copy.deepcopy(demo_session["stats"]),
        "candidates": copy.deepcopy(demo_session["candidates"]),
        "classification": copy.deepcopy(demo_session["classification"]),
        "activity": copy.deepcopy(demo_session["activity"]),
        "batches": copy.deepcopy(demo_session["batches"]),
        "processing_events": copy.deepcopy(demo_session["processing_events"]),
        "election": {
            "name": DEMO_ELECTION_NAME,
            "negeri": DEMO_STATE,
            "dun": f"{DEMO_DUN_CODE} {DEMO_DUN_NAME}",
            "dun_code": DEMO_DUN_CODE,
            "dun_name": DEMO_DUN_NAME,
            "batch": DEMO_BATCH_ID,
            "data_kind": "prototype_demo",
        },
        "flagged": copy.deepcopy(demo_session["flagged"]),
        "audit": audit,
        "imported": [],
        "notifications": [
            {
                "title": "Recognition engine",
                "body": "Not connected. This prototype uses simulated processing only.",
                "level": "warning",
            },
            {
                "title": "Review queue",
                "body": "Sample flagged ballots are waiting for officer review.",
                "level": "info",
            },
            {
                "title": "Demo mode",
                "body": "All counts, marks, and decisions are fictional.",
                "level": "info",
            },
        ],
        "settings": copy.deepcopy(DEFAULT_SETTINGS),
        "audit_counter": 1010,
        "ballot_counter": 3001,
    }


class Store(QObject):
    changed = Signal()
    message = Signal(str, str)  # text, level: success | warning | error | info

    def __init__(self) -> None:
        super().__init__()
        self._data = build_sample_data()
        self._load_settings()
        self._sync_election_from_settings()

    @property
    def data(self) -> dict:
        return self._data

    def settings(self) -> dict:
        return self._data["settings"]

    def _load_settings(self) -> None:
        path = settings_path()
        if not path.exists():
            return
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            self._data["settings"].update(saved)
        except (OSError, json.JSONDecodeError):
            pass

    def save_settings(self) -> None:
        path = settings_path()
        path.write_text(json.dumps(self._data["settings"], indent=2), encoding="utf-8")
        self.add_audit(
            user="Sahira",
            action="Saved application settings",
            related="SETTINGS",
            event_type="System Event",
            status="Completed",
            detail="Prototype settings written to data/settings.json.",
        )
        self.message.emit("Settings saved for this demonstration.", "success")
        self.changed.emit()

    def reset_settings(self) -> None:
        self._data["settings"] = copy.deepcopy(DEFAULT_SETTINGS)
        path = settings_path()
        if path.exists():
            path.unlink()
        self.message.emit("Settings restored to defaults.", "info")
        self.changed.emit()

    def current_location_key(self) -> str | None:
        election = self._data["election"]
        return location_key(election.get("negeri", ""), election.get("dun_code") or "")

    def _session_for(self, key: str | None) -> dict:
        if not key:
            return empty_session("not_applicable")
        sessions = self._data.setdefault("location_sessions", {})
        if key not in sessions:
            kind = "prototype_demo" if key == DEMO_LOCATION_KEY else "none"
            sessions[key] = empty_session(kind)
        return sessions[key]

    def _publish_session(self) -> None:
        key = self.current_location_key()
        session = self._session_for(key)
        self._data["stats"] = session["stats"]
        self._data["candidates"] = session["candidates"]
        self._data["classification"] = session["classification"]
        self._data["activity"] = session["activity"]
        self._data["batches"] = session["batches"]
        self._data["processing_events"] = session["processing_events"]
        self._data["flagged"] = session["flagged"]
        self._data["imported"] = session["imported"]
        election = self._data["election"]
        state = find_state(election.get("negeri", ""))
        state_code = state["code"] if state else "—"
        dun_code = election.get("dun_code") or "—"
        if not session.get("candidates"):
            session["candidates"] = build_candidate_records(state_code=state_code, dun_code=dun_code)
        for record in session["candidates"]:
            record["state_code"] = state_code
            record["dun_code"] = dun_code
            record["vote_count"] = int(record.get("vote_count", record.get("votes", 0)))
            record["name"] = record.get("candidate_name", record.get("name", ""))
            record["votes"] = record["vote_count"]
        pending = int(session["stats"].get("pending_reviews", 0))
        apply_result_status(
            session["candidates"],
            reviews_outstanding=pending,
            allow_leading=pending == 0 and any(int(item.get("vote_count", 0)) > 0 for item in session["candidates"]),
        )
        self._data["candidates"] = session["candidates"]
        if not dun_applicable(election.get("negeri", "")):
            election["data_kind"] = "not_applicable"
            election["batch"] = "—"
        elif session["kind"] == "none" and not session["stats"]["total_processed"] and not session["imported"]:
            election["data_kind"] = "none"
            election["batch"] = "—"
        elif session["kind"] == "imported_session":
            election["data_kind"] = "imported_session"
            election["batch"] = session["batches"][0]["id"] if session["batches"] else "IMPORTED"
        else:
            election["data_kind"] = session["kind"]
            if session["batches"]:
                election["batch"] = session["batches"][0]["id"]

    def _sync_election_from_settings(self) -> None:
        settings = self._data["settings"]
        negeri = settings.get("demo_negeri", DEMO_STATE)
        state = find_state(negeri)
        if state is None:
            negeri, dun_code, dun_name = DEMO_STATE, DEMO_DUN_CODE, DEMO_DUN_NAME
        elif not state.get("dun_applicable"):
            dun_code, dun_name = "", ""
        else:
            dun_code = settings.get("demo_dun_code", DEMO_DUN_CODE)
            seats = {item["code"]: item for item in state.get("constituencies", [])}
            if dun_code not in seats:
                first = state["constituencies"][0]
                dun_code, dun_name = first["code"], first["name"]
            else:
                dun_name = seats[dun_code]["name"]
        self._data["election"] = {
            "name": DEMO_ELECTION_NAME,
            "negeri": negeri,
            "dun": f"{dun_code} {dun_name}".strip(),
            "dun_code": dun_code,
            "dun_name": dun_name,
            "batch": DEMO_BATCH_ID,
            "data_kind": "prototype_demo",
        }
        self._publish_session()

    def set_demo_location(self, negeri: str, dun_code: str = "", dun_name: str = "") -> None:
        state = find_state(negeri)
        if state is None:
            return
        if not state.get("dun_applicable"):
            dun_code, dun_name = "", ""
        else:
            seats = {item["code"]: item for item in state.get("constituencies", [])}
            if dun_code not in seats:
                first = state["constituencies"][0] if state["constituencies"] else {"code": "", "name": ""}
                dun_code, dun_name = first["code"], first["name"]
            else:
                dun_name = seats[dun_code]["name"]
        self._data["settings"]["demo_negeri"] = negeri
        self._data["settings"]["demo_dun_code"] = dun_code
        self._data["settings"]["demo_dun_name"] = dun_name
        self._data["election"]["negeri"] = negeri
        self._data["election"]["dun_code"] = dun_code
        self._data["election"]["dun_name"] = dun_name
        self._data["election"]["dun"] = f"{dun_code} {dun_name}".strip()
        self._publish_session()
        self.changed.emit()

    def add_processing_event(self, description: str, batch: str, status: str) -> None:
        event = {
            "time": datetime.now().strftime("%H:%M"),
            "description": description,
            "batch": batch,
            "status": status,
        }
        session = self._session_for(self.current_location_key())
        session["processing_events"].insert(0, event)
        session["processing_events"] = session["processing_events"][:8]
        self._data["processing_events"] = session["processing_events"]

    def reset_demo_data(self) -> None:
        saved_settings = copy.deepcopy(self._data["settings"])
        self._data = build_sample_data()
        self._data["settings"] = saved_settings
        self._sync_election_from_settings()
        self.add_audit(
            user="Sahira",
            action="Cleared demonstration data",
            related="SYSTEM",
            event_type="System Event",
            status="Completed",
            detail="Sample ballots, results, and logs were reset. Not a production wipe.",
        )
        self.message.emit("Demonstration data cleared and sample records restored.", "success")
        self.changed.emit()

    def add_audit(self, user: str, action: str, related: str, event_type: str, status: str, detail: str) -> None:
        self._data["audit_counter"] += 1
        event = {
            "id": f"AUD-{self._data['audit_counter']}",
            "time": datetime.now(),
            "user": user,
            "action": action,
            "related": related,
            "type": event_type,
            "status": status,
            "detail": detail,
        }
        self._data["audit"].insert(0, event)
        self.changed.emit()

    def add_imported(self, paths: list[str], *, notify: bool = True) -> None:
        session = self._session_for(self.current_location_key())
        existing = {item["path"] for item in session["imported"]}
        added = 0
        for path in paths:
            path = str(path)
            if path in existing:
                continue
            session["imported"].append(
                {
                    "path": path,
                    "name": Path(path).name,
                    "location_key": self.current_location_key(),
                }
            )
            added += 1
        self._data["imported"] = session["imported"]
        if added:
            self.add_audit(
                user="Sahira",
                action="Imported ballot images",
                related="SCAN",
                event_type="Image Import",
                status="Completed",
                detail=f"{added} image file(s) added. Images are for demonstration only.",
            )
            if notify:
                self.message.emit(f"{added} ballot image(s) imported.", "success")
            self.changed.emit()

    def remove_imported(self, path: str) -> None:
        self._data["imported"] = [item for item in self._data["imported"] if item["path"] != path]
        self.changed.emit()

    def clear_imported(self) -> None:
        session = self._session_for(self.current_location_key())
        session["imported"] = []
        self._data["imported"] = session["imported"]
        self.message.emit("Image selection cleared.", "info")
        self.changed.emit()

    def complete_import_processing(
        self,
        processed_count: int,
        cancelled: bool = False,
        source_paths: list[str] | None = None,
        *,
        notify: bool = True,
    ) -> None:
        location = self.current_location_key()
        election = self._data["election"]
        batch_id = f"IMP-{datetime.now().strftime('%H%M%S')}"
        session = self._session_for(location)
        if session["kind"] in {"none", "not_applicable"}:
            session["kind"] = "imported_session"
        if cancelled:
            self.add_processing_event("Prototype processing cancelled by officer", batch_id, "Needs Review")
            self.add_audit(
                user="Sahira",
                action="Cancelled prototype processing",
                related=batch_id,
                event_type="Processing Simulation",
                status="Warning",
                detail="Officer cancelled the demonstration processing workflow. No recognition was performed.",
            )
            if notify:
                self.message.emit("Processing cancelled. No ballot was classified.", "warning")
            self._publish_session()
            self.changed.emit()
            return

        stats = session["stats"]
        stats["total_processed"] += processed_count
        stats["flagged"] += processed_count
        stats["pending_reviews"] += processed_count
        session["classification"]["needs_review"] = stats["flagged"]
        session["batches"].insert(
            0,
            {
                "id": batch_id,
                "time": datetime.now().strftime("%d %b %Y, %H:%M"),
                "images": processed_count,
                "valid": 0,
                "flagged": processed_count,
                "status": "Needs Review",
            },
        )
        imported = list(session["imported"])
        if source_paths is None:
            sources = [
                imported[index]["name"] if index < len(imported) else "imported image"
                for index in range(processed_count)
            ]
        else:
            sources = [Path(path).name for path in source_paths]
            if len(sources) < processed_count:
                sources.extend(["imported image"] * (processed_count - len(sources)))
            sources = sources[:processed_count]
        for index in range(processed_count):
            self._data["ballot_counter"] += 1
            ballot_id = f"BLT-{self._data['ballot_counter']}"
            source = sources[index]
            session["flagged"].insert(
                0,
                {
                    "id": ballot_id,
                    "batch": batch_id,
                    "reason": "Imported image queued for officer verification. No recognition engine was used.",
                    "confidence": None,
                    "status": "Pending Review",
                    "detected": "",
                    "notes": "",
                    "simulated": True,
                    "location_key": location,
                    "data_kind": "imported_session",
                    "source_file": source,
                },
            )
        self.add_processing_event(
            f"Imported image set queued for verification ({processed_count} file(s))",
            batch_id,
            "Needs Review",
        )
        self.add_audit(
            user="System",
            action="Prototype processing finished",
            related=batch_id,
            event_type="Processing Simulation",
            status="Completed",
            detail=(
                f"Demonstration workflow finished for {processed_count} image(s) at "
                f"{election.get('negeri')} {election.get('dun')}. "
                "Images were not classified as valid. No AI recognition was performed."
            ),
        )
        if notify:
            self.message.emit(
                "Prototype processing finished. Images were sent for officer verification — not classified as valid.",
                "warning",
            )
        self._publish_session()
        self.changed.emit()

    def submit_review(self, ballot_id: str, decision: str, notes: str) -> None:
        target = None
        for ballot in self._data["flagged"]:
            if ballot["id"] == ballot_id:
                target = ballot
                break
        if target is None:
            self.message.emit("Select a ballot before submitting a review.", "error")
            return

        was_pending = target["status"] == "Pending Review"
        target["status"] = "Reviewed"
        target["decision"] = decision
        target["notes"] = notes
        if was_pending:
            self._data["stats"]["pending_reviews"] = max(0, self._data["stats"]["pending_reviews"] - 1)
            if decision == "Mark as Rejected":
                self._data["stats"]["rejected"] += 1
                self._data["classification"]["rejected"] += 1
                self._data["stats"]["flagged"] = max(0, self._data["stats"]["flagged"] - 1)
                self._data["classification"]["needs_review"] = self._data["stats"]["flagged"]
            elif decision == "Confirm Detected Mark":
                self._data["stats"]["valid"] += 1
                self._data["classification"]["valid"] += 1
                self._data["stats"]["flagged"] = max(0, self._data["stats"]["flagged"] - 1)
                self._data["classification"]["needs_review"] = self._data["stats"]["flagged"]
                detected = target.get("detected", "")
                for candidate in self._data["candidates"]:
                    names = {candidate.get("candidate_name"), candidate.get("name")}
                    if detected in names:
                        candidate["vote_count"] = int(candidate.get("vote_count", 0)) + 1
                        candidate["votes"] = candidate["vote_count"]
                        break
        self._publish_session()

        self.add_audit(
            user="Sahira",
            action=decision,
            related=ballot_id,
            event_type="Review Decision",
            status="Completed",
            detail=f"Simulated review recorded. Notes: {notes or 'None'}",
        )
        self.message.emit(f"Review submitted for {ballot_id}. This is a simulated decision.", "success")
        self.changed.emit()

    def record_export(self, kind: str, path: str) -> None:
        self.add_audit(
            user="Sahira",
            action=f"Exported {kind}",
            related="EXPORT",
            event_type="CSV Export" if kind.lower().endswith("csv") else "System Event",
            status="Completed",
            detail=f"Prototype file written to {path}. Not an official election record.",
        )
        self.message.emit(f"{kind} exported.", "success")
        self.changed.emit()
