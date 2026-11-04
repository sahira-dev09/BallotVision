"""Build the local DUN JSON from the DOSM/SPR boundary table. Run once during development."""

from __future__ import annotations

import csv
import json
from collections import OrderedDict
from pathlib import Path

CSV_PATH = Path(
    r"C:\Users\ASUS\.cursor\projects\c-Users-ASUS-Documents-BallotVision\agent-tools\751856c2-1a55-4e9b-a1d1-4a7d2379ede1.txt"
)
DEST = Path(__file__).resolve().parents[1] / "data" / "malaysia_dun_constituencies.json"

STATE_ORDER = [
    "Perlis",
    "Kedah",
    "Kelantan",
    "Terengganu",
    "Pulau Pinang",
    "Perak",
    "Pahang",
    "Selangor",
    "Negeri Sembilan",
    "Melaka",
    "Johor",
    "Sabah",
    "Sarawak",
    "W.P. Kuala Lumpur",
    "W.P. Putrajaya",
    "W.P. Labuan",
]
STATE_CODES = {
    "Perlis": "PLS",
    "Kedah": "KDH",
    "Kelantan": "KTN",
    "Terengganu": "TRG",
    "Pulau Pinang": "PNG",
    "Perak": "PRK",
    "Pahang": "PHG",
    "Selangor": "SGR",
    "Negeri Sembilan": "NSN",
    "Melaka": "MLK",
    "Johor": "JHR",
    "Sabah": "SBH",
    "Sarawak": "SWK",
    "W.P. Kuala Lumpur": "KUL",
    "W.P. Putrajaya": "PJY",
    "W.P. Labuan": "LBN",
}
FEDERAL = {"W.P. Kuala Lumpur", "W.P. Putrajaya", "W.P. Labuan"}


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    states: OrderedDict[str, dict] = OrderedDict()
    for name in STATE_ORDER:
        states[name] = {
            "name": name,
            "code": STATE_CODES[name],
            "dun_applicable": name not in FEDERAL,
            "constituencies": [],
        }
    for row in rows:
        state_name = row["state"]
        code = (row.get("code_dun") or "").strip()
        dun = (row.get("dun") or "").strip()
        if not code or not dun:
            continue
        name = dun[len(code) :].strip() if dun.startswith(code) else dun.split(" ", 1)[-1]
        states[state_name]["constituencies"].append(
            {
                "code": code,
                "name": name,
                "label": f"{code} {name}",
                "parliament_code": (row.get("code_parlimen") or "").strip(),
                "parliament_name": (row.get("parlimen") or "").strip(),
            }
        )
    for state in states.values():
        seen: set[str] = set()
        unique = []
        for item in state["constituencies"]:
            if item["code"] in seen:
                continue
            seen.add(item["code"])
            unique.append(item)
        state["constituencies"] = unique
        state["dun_count"] = len(unique)

    payload = {
        "dataset": "Malaysian State Legislative Assembly (DUN/DN) constituencies",
        "effective_from": "2018-05-09",
        "effective_description": (
            "Post-2016 redelineation used for PRU-14 (2018) and PRU-15 (2022). "
            "Peninsular state elections 2023, Sabah 2020, and Sarawak 2021 used this DUN structure."
        ),
        "as_of": "2022-11-19",
        "sources": [
            {
                "name": "Department of Statistics Malaysia (DOSM) open geodata — state_parlimen_dun.csv",
                "url": "https://github.com/dosm-malaysia/data-open/blob/main/datasets/geodata/state_parlimen_dun.csv",
                "note": "Official Malaysian government open data joining SPR electoral boundaries.",
            },
            {
                "name": "Suruhanjaya Pilihan Raya Malaysia (SPR) — Senarai Bahagian Pilihan Raya (Dewan Undangan Negeri) bagi PRU ke-14",
                "url": "https://archive.data.gov.my/data/ms_MY/group/spr?tags=pilihanraya",
                "note": "Official SPR dataset published on data.gov.my / SPR open data holdings.",
            },
            {
                "name": "SPR Open Data Portal",
                "url": "https://opendata.spr.gov.my/",
                "note": "Constituency and election open data portal. This application does not live-query SPR.",
            },
        ],
        "notes": [
            "Federal Territories (W.P. Kuala Lumpur, W.P. Putrajaya, W.P. Labuan) have parliamentary seats only and no State Legislative Assembly (DUN).",
            "Constituency names and codes are copied from the DOSM/SPR boundary table. They are not election results.",
            "A later redelineation, if gazetted after this dataset date, is not reflected here.",
        ],
        "states": list(states.values()),
    }
    DEST.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", DEST)
    print("states", len(payload["states"]))
    print("total dun", sum(item["dun_count"] for item in payload["states"]))
    for state in payload["states"]:
        first = state["constituencies"][0]["label"] if state["constituencies"] else "-"
        print(f"{state['name']}: applicable={state['dun_applicable']} count={state['dun_count']} first={first}")


if __name__ == "__main__":
    main()
