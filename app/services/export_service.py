"""Write demonstration CSV and summary files. These are not official returns."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


NOTICE = "SIMULATED RESULTS — NOT OFFICIAL"


def export_results_csv(path: str, store_data: dict) -> None:
    valid = store_data["stats"]["valid"]
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        election = store_data.get("election", {})
        writer.writerow(["NOTICE", NOTICE])
        writer.writerow(["Generated", datetime.now().isoformat(timespec="seconds")])
        writer.writerow(["Election", election.get("name", "")])
        writer.writerow(["Negeri", election.get("negeri", "")])
        writer.writerow(["DUN", election.get("dun", "")])
        writer.writerow(["Dataset", election.get("data_kind", "simulated")])
        writer.writerow(["Percentages", "Share of valid votes"])
        writer.writerow([])
        writer.writerow(["Candidate ID", "Candidate", "Party", "Votes", "Percentage of valid votes"])
        for item in store_data["candidates"]:
            votes = int(item.get("vote_count", item.get("votes", 0)))
            percent = (votes / valid * 100) if valid else 0
            writer.writerow(
                [
                    item.get("candidate_id", ""),
                    item.get("candidate_name", item.get("name", "")),
                    item.get("party_name", ""),
                    votes,
                    f"{percent:.1f}%",
                ]
            )
        writer.writerow([])
        writer.writerow(["Metric", "Value"])
        stats = store_data["stats"]
        writer.writerow(["Total Ballots Counted", stats["total_processed"]])
        writer.writerow(["Valid Votes", stats["valid"]])
        writer.writerow(["Rejected Ballots", stats["rejected"]])
        writer.writerow(["Pending Reviews", stats["pending_reviews"]])


def export_results_summary(path: str, store_data: dict) -> None:
    stats = store_data["stats"]
    lines = [
        "BallotVision — Simulated Vote Summary",
        NOTICE,
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"Election: {store_data.get('election', {}).get('name', '')}",
        f"Negeri: {store_data.get('election', {}).get('negeri', '')}",
        f"DUN: {store_data.get('election', {}).get('dun', '')}",
        f"Dataset: {store_data.get('election', {}).get('data_kind', '')}",
        f"Total ballots counted: {stats['total_processed']}",
        f"Valid votes: {stats['valid']}",
        f"Rejected ballots: {stats['rejected']}",
        f"Pending reviews: {stats['pending_reviews']}",
        "",
        "Candidate totals (fictional demonstration names):",
        "Percentages are of valid votes.",
    ]
    valid = stats["valid"]
    for item in store_data["candidates"]:
        votes = int(item.get("vote_count", item.get("votes", 0)))
        percent = (votes / valid * 100) if valid else 0
        lines.append(
            f"- {item.get('candidate_name', item.get('name', ''))}: {votes} ({percent:.1f}%)"
        )
    lines.append("")
    lines.append("This file is a UI prototype export. It is not an official election result.")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def export_audit_csv(path: str, events: list[dict], time_format: str) -> None:
    from app.core.utils import format_timestamp

    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["NOTICE", "PROTOTYPE AUDIT LOG — NOT TAMPER-PROOF"])
        writer.writerow(["Timestamp", "Activity ID", "User", "Action", "Related", "Type", "Status", "Detail"])
        for event in events:
            writer.writerow(
                [
                    format_timestamp(event["time"], time_format),
                    event["id"],
                    event["user"],
                    event["action"],
                    event["related"],
                    event["type"],
                    event["status"],
                    event["detail"],
                ]
            )
