"""Compare observed names with the official candidate list.

This does not read marks and does not count votes. A future recogniser can pass
names it actually read. Matching is exact, so an unknown name is never assigned
to a different registered candidate.
"""

from __future__ import annotations

from dataclasses import dataclass

NOT_PERFORMED = "not_performed"
CONSISTENT = "consistent"
MISMATCH = "mismatch"
MISMATCH_REASON = (
    "A name on this ballot is not in the registered candidate list. "
    "Manual investigation is required."
)


@dataclass(frozen=True)
class CandidateComparison:
    matched: tuple[str, ...]
    unknown: tuple[str, ...]
    status: str

    @property
    def mismatched(self) -> bool:
        return self.status == MISMATCH


def compare_candidates(observed: list[str] | tuple[str, ...], official: list[str] | tuple[str, ...]) -> CandidateComparison:
    """Exact name comparison. Partial or similar names stay unknown."""
    official_names: dict[str, str] = {}
    for raw in official:
        name = (raw or "").strip()
        if name:
            official_names.setdefault(name.casefold(), name)
    matched: list[str] = []
    unknown: list[str] = []
    seen_matched: set[str] = set()
    seen_unknown: set[str] = set()
    for raw in observed:
        name = (raw or "").strip()
        if not name:
            continue
        hit = official_names.get(name.casefold())
        if hit:
            if hit not in seen_matched:
                matched.append(hit)
                seen_matched.add(hit)
        elif name.casefold() not in seen_unknown:
            unknown.append(name)
            seen_unknown.add(name.casefold())
    if unknown:
        status = MISMATCH
    elif matched:
        status = CONSISTENT
    else:
        status = NOT_PERFORMED
    return CandidateComparison(matched=tuple(matched), unknown=tuple(unknown), status=status)
