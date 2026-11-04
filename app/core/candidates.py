"""Fictional demonstration candidates. Not real politicians or SPR nominees."""

from __future__ import annotations

from copy import deepcopy

# Distinctly fictional names, parties, and portrait IDs for the prototype only.
DEMO_CANDIDATES = (
    {
        "candidate_id": "CAN-D01",
        "candidate_name": "Amalia Suria",
        "party_name": "Demo Civic League",
        "ballot_position": 1,
        "portrait_file": "Nur_Lyana_Yasmin.jpeg",
        "accent": "#22D3EE",
    },
    {
        "candidate_id": "CAN-D02",
        "candidate_name": "Rizal Purnama",
        "party_name": "Independent (Demo)",
        "ballot_position": 2,
        "portrait_file": "Muhammad_Ruzaiman.jpeg",
        "accent": "#34D399",
    },
    {
        "candidate_id": "CAN-D03",
        "candidate_name": "Nora Bentara",
        "party_name": "Demo Harmony Front",
        "ballot_position": 3,
        "portrait_file": "can_d03.svg",
        "accent": "#FBBF24",
    },
    {
        "candidate_id": "CAN-D04",
        "candidate_name": "Faizal Ombak",
        "party_name": "Demo Workers Circle",
        "ballot_position": 4,
        "portrait_file": "can_d04.svg",
        "accent": "#A78BFA",
    },
)

DEMO_VOTE_COUNTS = {
    "CAN-D01": 912,
    "CAN-D02": 754,
    "CAN-D03": 481,
    "CAN-D04": 244,
}


def candidate_names() -> tuple[str, ...]:
    return tuple(item["candidate_name"] for item in DEMO_CANDIDATES)


def build_candidate_records(
    *,
    state_code: str,
    dun_code: str,
    votes: dict[str, int] | None = None,
    data_source: str = "BallotVision prototype",
    dataset_type: str = "simulated",
) -> list[dict]:
    counts = votes if votes is not None else {item["candidate_id"]: 0 for item in DEMO_CANDIDATES}
    records = []
    for item in DEMO_CANDIDATES:
        record = deepcopy(item)
        record.update(
            {
                "state_code": state_code,
                "dun_code": dun_code,
                "vote_count": int(counts.get(item["candidate_id"], 0)),
                "result_status": "none",
                "data_source": data_source,
                "dataset_type": dataset_type,
                "portrait_path": f"images/candidates/{item['portrait_file']}",
            }
        )
        records.append(record)
    return apply_result_status(records, reviews_outstanding=0, allow_leading=False)


def apply_result_status(
    records: list[dict],
    *,
    reviews_outstanding: int,
    allow_leading: bool,
) -> list[dict]:
    ordered = sorted(records, key=lambda item: (-int(item.get("vote_count", 0)), item["ballot_position"]))
    if not ordered:
        return records
    top = int(ordered[0].get("vote_count", 0))
    tied = sum(1 for item in ordered if int(item.get("vote_count", 0)) == top) > 1
    for item in records:
        votes = int(item.get("vote_count", 0))
        if reviews_outstanding > 0 or not allow_leading or votes <= 0:
            item["result_status"] = "none"
        elif tied and votes == top:
            item["result_status"] = "tied"
        elif votes == top:
            item["result_status"] = "leading"
        else:
            item["result_status"] = "trailing"
    return records


def leading_record(records: list[dict]) -> dict | None:
    leaders = [item for item in records if item.get("result_status") == "leading"]
    return leaders[0] if len(leaders) == 1 else None
