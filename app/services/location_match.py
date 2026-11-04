"""Match OCR text to the bundled Negeri and DUN dataset.

Suggestions are evidence from the text only. A weak or conflicting reading does not
produce a Negeri or DUN.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.constituencies import constituencies_for, dun_applicable, states

HIGH = "High confidence"
LOW = "Low confidence"
NOT_DETECTED = "Not detected"

_CODE_PATTERN = re.compile(r"(?<![a-z0-9])n\s*\.?\s*(\d{1,2})(?!\d)", re.IGNORECASE)


@dataclass(frozen=True)
class LocationMatch:
    negeri: str | None
    negeri_code: str | None
    dun_code: str | None
    dun_name: str | None
    status: str
    negeri_status: str
    dun_status: str
    reason: str


def match_location(text: str) -> LocationMatch:
    raw = text or ""
    if not raw.strip():
        return _result(
            status=NOT_DETECTED,
            negeri_status=NOT_DETECTED,
            dun_status=NOT_DETECTED,
            reason="No text was available to match.",
        )

    folded = raw.casefold()
    state_hits = _state_hits(folded)
    codes = _dun_codes(raw)
    seat_hits = _seat_hits(folded)

    negeri, negeri_status, negeri_reason = _choose_negeri(state_hits, seat_hits)
    if negeri is None:
        if codes and negeri_status == NOT_DETECTED:
            listed = ", ".join(codes)
            return _result(
                status=LOW,
                negeri_status=LOW,
                dun_status=LOW,
                reason=f"DUN code {listed} appears without a Negeri, so no constituency was suggested.",
            )
        return _result(
            status=NOT_DETECTED if negeri_status == NOT_DETECTED else LOW,
            negeri_status=negeri_status,
            dun_status=NOT_DETECTED,
            reason=negeri_reason,
        )

    if not dun_applicable(negeri):
        return _result(
            negeri=negeri,
            negeri_code=_state_code(negeri),
            status=HIGH,
            negeri_status=HIGH,
            dun_status=NOT_DETECTED,
            reason=f"{negeri} has parliamentary seats only. No DUN was suggested.",
        )

    dun_code, dun_name, dun_status, dun_reason = _choose_dun(negeri, codes, seat_hits)
    if dun_status == HIGH and negeri_status == HIGH:
        reason = f"Matched {negeri} {dun_code} {dun_name}."
        status = HIGH
    elif dun_status == NOT_DETECTED and not codes and not _names_in_state(negeri, seat_hits):
        reason = f"Negeri matches {negeri}, but no DUN code or constituency name was found."
        status = LOW
    else:
        reason = dun_reason
        status = LOW
    return _result(
        negeri=negeri,
        negeri_code=_state_code(negeri),
        dun_code=dun_code,
        dun_name=dun_name,
        status=status,
        negeri_status=negeri_status,
        dun_status=dun_status,
        reason=reason,
    )


def _result(
    *,
    negeri: str | None = None,
    negeri_code: str | None = None,
    dun_code: str | None = None,
    dun_name: str | None = None,
    status: str | None = None,
    negeri_status: str,
    dun_status: str,
    reason: str,
) -> LocationMatch:
    if status is None:
        status = LOW
    return LocationMatch(
        negeri=negeri,
        negeri_code=negeri_code,
        dun_code=dun_code,
        dun_name=dun_name,
        status=status,
        negeri_status=negeri_status,
        dun_status=dun_status,
        reason=reason,
    )


def _choose_negeri(state_hits: dict[str, str], seat_hits: list[dict]) -> tuple[str | None, str, str]:
    explicit = set(state_hits)
    inferred = {hit["state"] for hit in seat_hits}
    if len(explicit) > 1:
        names = ", ".join(sorted(explicit))
        return None, LOW, f"More than one Negeri matches: {names}."
    if len(explicit) == 1:
        negeri = next(iter(explicit))
        other = inferred - {negeri}
        if other:
            names = ", ".join(sorted(other))
            return (
                None,
                LOW,
                f"The text matches {negeri} and also a constituency in {names}.",
            )
        return negeri, HIGH, f"Negeri matches {negeri}."
    if len(inferred) == 1:
        negeri = next(iter(inferred))
        return negeri, HIGH, f"Negeri matches {negeri} from the constituency name."
    if len(inferred) > 1:
        names = ", ".join(sorted(inferred))
        return None, LOW, f"Constituency names match more than one Negeri: {names}."
    return None, NOT_DETECTED, "No Negeri was detected."


def _choose_dun(
    negeri: str,
    codes: list[str],
    seat_hits: list[dict],
) -> tuple[str | None, str | None, str, str]:
    seats = {item["code"]: item for item in constituencies_for(negeri)}
    names = _names_in_state(negeri, seat_hits)
    unknown = [code for code in codes if code not in seats]
    known = [code for code in codes if code in seats]
    if unknown and not known:
        listed = ", ".join(unknown)
        return None, None, LOW, f"{listed} is not a DUN in {negeri}."
    if len(known) > 1:
        listed = ", ".join(known)
        return None, None, LOW, f"More than one DUN code matches in {negeri}: {listed}."
    if len(names) > 1 and not known:
        listed = ", ".join(sorted(item["name"] for item in names))
        return None, None, LOW, f"More than one constituency name matches in {negeri}: {listed}."
    if len(known) == 1:
        seat = seats[known[0]]
        if names and any(item["code"] != seat["code"] for item in names):
            other = ", ".join(sorted(item["name"] for item in names if item["code"] != seat["code"]))
            return (
                None,
                None,
                LOW,
                f"{seat['code']} in {negeri} is {seat['name']}, but the text also matches {other}.",
            )
        return seat["code"], seat["name"], HIGH, f"Matched {seat['label']}."
    if len(names) == 1:
        seat = names[0]
        return seat["code"], seat["name"], HIGH, f"Matched {seat['label']} from the constituency name."
    return None, None, NOT_DETECTED, f"No DUN was detected for {negeri}."


def _names_in_state(negeri: str, seat_hits: list[dict]) -> list[dict]:
    found: dict[str, dict] = {}
    for hit in seat_hits:
        if hit["state"] == negeri:
            found[hit["code"]] = hit
    return list(found.values())


def _state_code(name: str) -> str | None:
    for state in states():
        if state["name"] == name:
            return state.get("code")
    return None


def _state_hits(folded: str) -> dict[str, str]:
    found: dict[str, tuple[int, int]] = {}
    spans: list[tuple[int, int, str]] = []
    for state in states():
        for phrase in _state_phrases(state):
            for start, end in _phrase_spans(folded, phrase):
                spans.append((start, end, state["name"]))
    for start, end, name in _without_shorter_spans(spans):
        previous = found.get(name)
        if previous is None or end - start > previous[1] - previous[0]:
            found[name] = (start, end)
    return {name: name for name in found}


def _state_phrases(state: dict) -> list[str]:
    phrases = [state["name"]]
    code = state.get("code") or ""
    if code:
        phrases.append(code)
    if state["name"].startswith("W.P. "):
        phrases.append(state["name"].removeprefix("W.P. ").strip())
    return phrases


def _seat_hits(folded: str) -> list[dict]:
    spans: list[tuple[int, int, dict]] = []
    for state in states():
        for seat in state.get("constituencies") or []:
            record = {
                "state": state["name"],
                "code": seat["code"],
                "name": seat["name"],
                "label": seat.get("label") or f"{seat['code']} {seat['name']}",
            }
            for start, end in _phrase_spans(folded, seat["name"]):
                spans.append((start, end, record))
    kept: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for _start, _end, record in _without_shorter_spans(spans):
        key = (record["state"], record["code"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(record)
    return kept


def _dun_codes(text: str) -> list[str]:
    found: list[str] = []
    for match in _CODE_PATTERN.finditer(text):
        code = f"N.{int(match.group(1)):02d}"
        if code not in found:
            found.append(code)
    return found


def _phrase_spans(folded: str, phrase: str) -> list[tuple[int, int]]:
    parts = re.findall(r"[a-z0-9]+", phrase.casefold())
    if not parts:
        return []
    body = r"\s+".join(re.escape(part) for part in parts)
    pattern = re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")
    return [(match.start(), match.end()) for match in pattern.finditer(folded)]


def _without_shorter_spans(spans: list[tuple[int, int, object]]) -> list[tuple[int, int, object]]:
    kept: list[tuple[int, int, object]] = []
    for start, end, value in spans:
        covered = False
        for other_start, other_end, _other in spans:
            if other_start <= start and other_end >= end and (other_end - other_start) > (end - start):
                covered = True
                break
        if not covered:
            kept.append((start, end, value))
    return kept
