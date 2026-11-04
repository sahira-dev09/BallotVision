"""Offline checks for the DUN dataset and officer photo."""

from collections import Counter
from pathlib import Path

from app.core.candidates import DEMO_CANDIDATES
from app.core.constituencies import dun_applicable, load_dataset, states
from app.core.utils import asset_path
from app.widgets.avatar import profile_image_path

EXPECTED = {
    "Perlis": 15,
    "Kedah": 36,
    "Kelantan": 45,
    "Terengganu": 32,
    "Pulau Pinang": 40,
    "Perak": 59,
    "Pahang": 42,
    "Selangor": 56,
    "Negeri Sembilan": 36,
    "Melaka": 28,
    "Johor": 56,
    "Sabah": 73,
    "Sarawak": 82,
    "W.P. Kuala Lumpur": 0,
    "W.P. Putrajaya": 0,
    "W.P. Labuan": 0,
}


def main() -> None:
    data = load_dataset()
    names = [item["name"] for item in states()]
    assert names == list(EXPECTED), names
    total = 0
    for item in states():
        count = item["dun_count"]
        assert count == EXPECTED[item["name"]], (item["name"], count)
        assert dun_applicable(item["name"]) == (count > 0)
        codes = [seat["code"] for seat in item["constituencies"]]
        assert len(codes) == len(set(codes))
        total += count
    assert total == 600, total
    photo = profile_image_path()
    assert photo.exists(), photo
    portraits = [asset_path("images", "candidates", item["portrait_file"]) for item in DEMO_CANDIDATES]
    assert all(path.exists() for path in portraits), portraits
    print("states", len(names))
    print("total_dun", total)
    print("photo", photo, photo.stat().st_size)
    print("as_of", data.get("as_of"))
    print("ok")


if __name__ == "__main__":
    main()
