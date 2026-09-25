"""Reconcile CTAD extraction IDs before publishing a refreshed program.

The CTAD PDFs may renumber talks as well as sessions. The currently published
program is the identity authority: exact unique talk titles retain their app
ids, sessions follow their retained children or unambiguous schedule context,
and genuinely new colliding source ids receive deterministic app ids.
"""

from __future__ import annotations

import argparse
import copy
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


def _fresh_id(
    item: dict[str, Any], reserved: set[str], used: set[str]
) -> str:
    """Allocate a deterministic app id for a new item whose source id collides."""
    prefix = {"session": "s", "poster-session": "s", "talk": "t", "poster": "p"}[
        item["kind"]
    ]
    seed = "\0".join(
        [
            item["kind"],
            normalize_title(item["title"]),
            item.get("date", ""),
            item.get("starts_at", ""),
            item["id"],
        ]
    )
    base = f"{prefix}-{hashlib.sha256(seed.encode()).hexdigest()[:12]}"
    candidate = base
    suffix = 2
    while candidate in reserved or candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def _unique_title_matches(
    baseline_items: list[dict[str, Any]], candidate_items: list[dict[str, Any]]
) -> dict[int, str]:
    """Map candidate object identities to old ids for unique exact titles."""
    old_by_title: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    new_by_title: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in baseline_items:
        old_by_title[(item["kind"], normalize_title(item["title"]))].append(item)
    for item in candidate_items:
        new_by_title[(item["kind"], normalize_title(item["title"]))].append(item)
    matches: dict[int, str] = {}
    for key in old_by_title.keys() & new_by_title.keys():
        old = old_by_title[key]
        new = new_by_title[key]
        if len(old) == len(new) == 1:
            matches[id(new[0])] = old[0]["id"]
    return matches


def reconcile_identities(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    """Carry published identities onto an extracted refresh when matches are exact."""
    reconciled = copy.deepcopy(candidate)
    old_records = item_records(baseline)
    reserved = set(old_records)
    used: set[str] = set()

    old_presentations = [
        item for item in old_records.values() if item["kind"] in {"talk", "poster"}
    ]
    new_presentations = [
        item
        for session in reconciled["sessions"]
        for item in session["presentations"]
    ]
    presentation_matches = _unique_title_matches(
        old_presentations, new_presentations
    )
    for item in new_presentations:
        old = old_records.get(item["id"])
        if (
            old is not None
            and old["kind"] == item["kind"]
            and normalize_title(old["title"]) == normalize_title(item["title"])
        ):
            presentation_matches[id(item)] = old["id"]
    matched_presentations = 0
    fresh_presentations = 0
    for item in new_presentations:
        old_id = presentation_matches.get(id(item))
        if old_id is not None and old_id not in used:
            item["id"] = old_id
            matched_presentations += 1
        elif item["id"] in reserved or item["id"] in used:
            item["id"] = _fresh_id(item, reserved, used)
            fresh_presentations += 1
        used.add(item["id"])

    old_sessions = list(baseline["sessions"])
    new_sessions = list(reconciled["sessions"])
    old_parent_by_child = {
        item["id"]: session["id"]
        for session in old_sessions
        for item in session["presentations"]
    }

    child_claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
    child_target: dict[int, str] = {}
    for session in new_sessions:
        parents = {
            old_parent_by_child[item["id"]]
            for item in session["presentations"]
            if item["id"] in old_parent_by_child
        }
        if len(parents) == 1:
            target = parents.pop()
            child_target[id(session)] = target
            child_claims[target].append(session)

    session_matches: dict[int, str] = {
        object_id: target
        for object_id, target in child_target.items()
        if len(child_claims[target]) == 1
    }
    claimed_old_sessions = set(session_matches.values())

    def add_unique_matches(key: Any) -> None:
        old_by_key: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        new_by_key: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for session in old_sessions:
            if session["id"] not in claimed_old_sessions:
                old_by_key[key(session)].append(session)
        for session in new_sessions:
            if id(session) not in session_matches:
                new_by_key[key(session)].append(session)
        for value in old_by_key.keys() & new_by_key.keys():
            old = old_by_key[value]
            new = new_by_key[value]
            if len(old) == len(new) == 1:
                session_matches[id(new[0])] = old[0]["id"]
                claimed_old_sessions.add(old[0]["id"])

    add_unique_matches(
        lambda session: (
            session["kind"],
            session["date"],
            session.get("starts_at", ""),
        )
    )
    add_unique_matches(
        lambda session: (session["kind"], normalize_title(session["title"]))
    )

    matched_sessions = 0
    fresh_sessions = 0
    for session in new_sessions:
        old_id = session_matches.get(id(session))
        if old_id is not None and old_id not in used:
            session["id"] = old_id
            matched_sessions += 1
        elif session["id"] in reserved or session["id"] in used:
            session["id"] = _fresh_id(session, reserved, used)
            fresh_sessions += 1
        used.add(session["id"])

    return reconciled, {
        "matched_presentations": matched_presentations,
        "fresh_presentations": fresh_presentations,
        "matched_sessions": matched_sessions,
        "fresh_sessions": fresh_sessions,
    }


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


def publication_blockers(report: dict[str, Any]) -> list[str]:
    """Block only unresolved identity changes that could misplace user content."""
    blockers = [
        f"{row['id']}: possible positional ID reuse"
        for row in report["possible_id_reuse"]
        if sum(row["references"].values()) > 0
    ]
    for row in report["removed"]:
        if sum(row["references"].values()) > 0:
            blockers.append(f"{row['id']}: removed item has {_references(row)}")
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
        help="fail when referenced content cannot be reconciled safely",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write the identity-reconciled candidate when review succeeds",
    )
    arguments = parser.parse_args(argv)

    baseline = load_json(arguments.baseline)
    extracted_candidate = load_json(arguments.candidate)
    snapshot = load_json(arguments.notebook_snapshot)
    candidate, identity_summary = reconcile_identities(
        baseline, extracted_candidate
    )
    print(
        "Identity reconciliation: "
        f"{identity_summary['matched_presentations']} presentations and "
        f"{identity_summary['matched_sessions']} sessions retained published ids; "
        f"{identity_summary['fresh_presentations']} new presentations and "
        f"{identity_summary['fresh_sessions']} new sessions received app ids."
    )
    result = compare(
        baseline, candidate, snapshot, str(arguments.notebook_snapshot)
    )
    print(render(result), end="")
    blockers = publication_blockers(result)
    if arguments.strict and blockers:
        print("Publication blocked:", file=sys.stderr)
        for blocker in blockers:
            print(f"- {blocker}", file=sys.stderr)
        return 1
    if arguments.output:
        arguments.output.write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
