"""Load the bundled Malaysian Negeri/DUN dataset. Offline only — no SPR live feed."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.utils import bundled_data_path

DATASET_NAME = "malaysia_dun_constituencies.json"


@lru_cache(maxsize=1)
def load_dataset() -> dict:
    path = bundled_data_path(DATASET_NAME)
    if not path.exists():
        return {
            "dataset": "Malaysian DUN constituencies",
            "as_of": "unavailable",
            "effective_description": "Dataset file is missing.",
            "sources": [],
            "notes": ["The local constituency file could not be loaded."],
            "states": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def states() -> list[dict]:
    return list(load_dataset().get("states", []))


def state_names() -> list[str]:
    return [item["name"] for item in states()]


def find_state(name: str) -> dict | None:
    for item in states():
        if item["name"] == name:
            return item
    return None


def constituencies_for(state_name: str) -> list[dict]:
    state = find_state(state_name)
    if not state:
        return []
    return list(state.get("constituencies", []))


def dun_applicable(state_name: str) -> bool:
    state = find_state(state_name)
    return bool(state and state.get("dun_applicable"))


def location_key(state_name: str, dun_code: str | None) -> str | None:
    if not state_name or not dun_code:
        return None
    return f"{state_name}|{dun_code}"


def default_location() -> tuple[str, str, str]:
    state = find_state("Johor") or (states()[0] if states() else None)
    if not state:
        return ("Johor", "N.01", "Buloh Kasap")
    seats = state.get("constituencies") or []
    if not seats:
        return (state["name"], "", "")
    first = seats[0]
    return (state["name"], first["code"], first["name"])


def source_label() -> str:
    data = load_dataset()
    as_of = data.get("as_of", "")
    return f"Electoral boundaries: post-2016 redelineation · as of {as_of} · DOSM/SPR open data · not a live SPR feed"


def dataset_path() -> Path:
    return bundled_data_path(DATASET_NAME)
