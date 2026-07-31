"""Review CTAD positional IDs before publishing a refreshed program.

The CTAD PDFs provide stable labels for talks and posters, but not for sessions.
This comparison treats the currently published program as the identity
authority and highlights positional IDs that may now name different content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

CONFERENCE_ID = "ctad-2026"
COMPARE_FIELDS = (
    "kind",
    "title",
    "date",
    "starts_at",
    "ends_at",
    "location",
    "parent_id",
    "presentation_ids",
    "speaker_ids",
    "description_html",
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def publication_hash(program: dict[str, Any]) -> str:
    """Reproduce the hash of the compact JSON uploaded by the publisher."""
    encoded = json.dumps(
        program, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_title(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def item_records(program: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for session in program["sessions"]:
        session_id = session["id"]
        records[session_id] = {
            "id": session_id,
            "kind": session["kind"],
            "title": session["title"],
            "date": session["date"],
            "starts_at": session.get("starts_at", ""),
            "ends_at": session.get("ends_at", ""),
            "location": session.get("location", ""),
            "parent_id": "",
            "presentation_ids": [
                presentation["id"] for presentation in session["presentations"]
            ],
            "speaker_ids": sorted(session.get("speaker_ids", [])),
            "description_html": session.get("description_html", ""),
        }
        for presentation in session["presentations"]:
            presentation_id = presentation["id"]
            records[presentation_id] = {
                "id": presentation_id,
                "kind": presentation["kind"],
                "title": presentation["title"],
                "date": session["date"],
                "starts_at": presentation.get("starts_at", ""),
                "ends_at": presentation.get("ends_at", ""),
                "location": presentation.get("location", ""),
                "parent_id": session_id,
                "presentation_ids": [],
                "speaker_ids": sorted(presentation.get("speaker_ids", [])),
                "description_html": presentation.get("description_html", ""),
            }
    return records


def snapshot_references(
    snapshot: Any, baseline_hash: str, source: str
) -> dict[str, dict[str, int]]:
    try:
        if snapshot["conference_id"] != CONFERENCE_ID:
            raise TypeError(f"conference_id must be {CONFERENCE_ID}")
        if snapshot["program_version"] != baseline_hash:
            raise TypeError("program_version does not match the baseline program")
        if not isinstance(snapshot["exported_at"], str):
            raise TypeError("exported_at must be a string")
        notes = snapshot["notes"]
        rsvps = snapshot["rsvps"]
        if not isinstance(notes, list) or not isinstance(rsvps, list):
            raise TypeError("notes and rsvps must be lists")
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid notebook snapshot {source}: {exc}") from exc

    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"notes": 0, "rsvps": 0}
    )
    try:
        for note in notes:
            item_id = note["item_id"]
            if not isinstance(item_id, str) or not item_id:
                raise TypeError("note item_id must be a non-empty string")
            counts[item_id]["notes"] += 1
        for rsvp in rsvps:
            item_id = rsvp["item_id"]
            if not isinstance(item_id, str) or not item_id:
                raise TypeError("rsvp item_id must be a non-empty string")
            counts[item_id]["rsvps"] += 1
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid notebook snapshot {source}: {exc}") from exc
    return dict(counts)


def changed_fields(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    return [field for field in COMPARE_FIELDS if old[field] != new[field]]


def possible_id_reuse(old: dict[str, Any], new: dict[str, Any]) -> bool:
    """Detect an unchanged id that now appears to describe another item."""
    if old["kind"] != new["kind"]:
        return True
    old_title = normalize_title(old["title"])
    new_title = normalize_title(new["title"])
    similarity = SequenceMatcher(None, old_title, new_title).ratio()
    speakers_overlap = bool(set(old["speaker_ids"]) & set(new["speaker_ids"]))
    old_children = set(old["presentation_ids"])
    new_children = set(new["presentation_ids"])
    children_replaced = bool(
        old_children and new_children and old_children.isdisjoint(new_children)
    )
    return children_replaced or (similarity < 0.35 and not speakers_overlap)


def compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    snapshot: Any,
    snapshot_source: str = "<snapshot>",
) -> dict[str, Any]:
    """Compare programs and attach notebook reference counts to every change."""
    if baseline["conference"]["id"] != CONFERENCE_ID:
        raise ValueError(f"baseline conference must be {CONFERENCE_ID}")
    if candidate["conference"]["id"] != CONFERENCE_ID:
        raise ValueError(f"candidate conference must be {CONFERENCE_ID}")

    old_items = item_records(baseline)
    new_items = item_records(candidate)
    old_ids = set(old_items)
    new_ids = set(new_items)
    baseline_hash = publication_hash(baseline)
    references = snapshot_references(snapshot, baseline_hash, snapshot_source)

    def reference_counts(item_id: str) -> dict[str, int]:
        return references.get(item_id, {"notes": 0, "rsvps": 0})

    added = [new_items[item_id] for item_id in sorted(new_ids - old_ids)]
    removed = [
        {
            **old_items[item_id],
            "references": reference_counts(item_id),
        }
        for item_id in sorted(old_ids - new_ids)
    ]
    modified: list[dict[str, Any]] = []
    reused: list[dict[str, Any]] = []
    for item_id in sorted(old_ids & new_ids):
        old = old_items[item_id]
        new = new_items[item_id]
        fields = changed_fields(old, new)
        if not fields:
            continue
        row = {
            "id": item_id,
            "kind": old["kind"],
            "old_title": old["title"],
            "new_title": new["title"],
            "fields": fields,
            "references": reference_counts(item_id),
        }
        modified.append(row)
        if possible_id_reuse(old, new):
            reused.append(row)

    orphaned = sorted(set(references) - old_ids)
    affected = [
        item
        for item in [*removed, *modified]
        if sum(item["references"].values()) > 0
    ]
    return {
        "baseline_hash": baseline_hash,
        "candidate_hash": publication_hash(candidate),
        "summary": {
            "stable_ids": len(old_ids & new_ids),
            "added_ids": len(added),
            "removed_ids": len(removed),
            "modified_ids": len(modified),
            "possible_id_reuse": len(reused),
            "items_with_user_content": len(affected),
        },
        "added": added,
        "removed": removed,
        "modified": modified,
        "possible_id_reuse": reused,
        "items_with_user_content": affected,
        "orphaned_notebook_ids": orphaned,
    }


def _references(row: dict[str, Any]) -> str:
    return (
        f"{row['references']['notes']} note(s), "
        f"{row['references']['rsvps']} RSVP(s)"
    )


def render(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# CTAD program identity review",
        "",
        f"- Stable IDs: {summary['stable_ids']}",
        f"- Added IDs: {summary['added_ids']}",
        f"- Removed IDs: {summary['removed_ids']}",
        f"- Modified IDs: {summary['modified_ids']}",
        f"- Possible positional ID reuse: {summary['possible_id_reuse']}",
        f"- Changed/removed items with user content: "
        f"{summary['items_with_user_content']}",
    ]

    def section(title: str, rows: list[dict[str, Any]], formatter: Any) -> None:
        if rows:
            lines.extend(["", f"## {title}", ""])
            lines.extend(f"- {formatter(row)}" for row in rows)

    section(
        "Possible positional ID reuse",
        report["possible_id_reuse"],
        lambda row: (
            f"`{row['id']}`: {row['old_title']} → {row['new_title']} "
            f"({_references(row)})"
        ),
    )
    section(
        "Removed IDs",
        report["removed"],
        lambda row: f"`{row['id']}`: {row['title']} ({_references(row)})",
    )
    section(
        "Modified IDs",
        report["modified"],
        lambda row: (
            f"`{row['id']}`: {', '.join(row['fields'])} "
            f"({_references(row)})"
        ),
    )
    section(
        "Added IDs",
        report["added"],
        lambda row: f"`{row['id']}`: {row['title']}",
    )
    if report["orphaned_notebook_ids"]:
        lines.extend(
            [
                "",
                "> Warning: the notebook already references IDs absent from the "
                "baseline: "
                + ", ".join(report["orphaned_notebook_ids"]),
            ]
        )
    return "\n".join(lines) + "\n"


def publication_blockers(
    report: dict[str, Any], allowed_content_changes: set[str]
) -> list[str]:
    """Return identity or user-content conflicts that make publication unsafe."""
    blockers = [
        f"{row['id']}: possible positional ID reuse"
        for row in report["possible_id_reuse"]
    ]
    reused_ids = {row["id"] for row in report["possible_id_reuse"]}
    for row in report["removed"]:
        if sum(row["references"].values()) > 0:
            blockers.append(f"{row['id']}: removed item has {_references(row)}")
    for row in report["modified"]:
        if (
            row["id"] not in reused_ids
            and row["id"] not in allowed_content_changes
            and sum(row["references"].values()) > 0
        ):
            blockers.append(f"{row['id']}: changed item has {_references(row)}")
    return blockers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="currently published program JSON")
    parser.add_argument("candidate", type=Path, help="rebuilt candidate program JSON")
    parser.add_argument(
        "--notebook-snapshot",
        required=True,
        type=Path,
        help="fresh conference-scoped notebook export",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail on possible ID reuse or unreviewed user-content impact",
    )
    parser.add_argument(
        "--allow-content-change",
        action="append",
        default=[],
        metavar="ITEM_ID",
        help="acknowledge a non-identity change to an item with user content",
    )
    arguments = parser.parse_args(argv)

    baseline = load_json(arguments.baseline)
    candidate = load_json(arguments.candidate)
    snapshot = load_json(arguments.notebook_snapshot)
    result = compare(
        baseline, candidate, snapshot, str(arguments.notebook_snapshot)
    )
    print(render(result), end="")
    blockers = publication_blockers(result, set(arguments.allow_content_change))
    if arguments.strict and blockers:
        print("Publication blocked:", file=sys.stderr)
        for blocker in blockers:
            print(f"- {blocker}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
