"""Stage, compare, and explicitly promote a full AAIC program refresh."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from scripts.export_presentations_by_date import rows_by_date, write_csvs
from scripts.export_sqlite import export_sqlite
from scripts.scrape_aaic import write_outputs

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "aaic_2026"
DEFAULT_REFRESH_ROOT = ROOT / ".refresh"
NOTEBOOK_URL = "https://aaic2026.kozak.ch/api/notebook/export.json"
REPORT_JSON = "report.json"
REPORT_MD = "report.md"
STAGED_NOTEBOOK = "notebook-snapshot.json"
SOURCE_FILES = ("sessions.json", "people.json")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def content_hash(directory: Path) -> str:
    digest = hashlib.sha256()
    for name in SOURCE_FILES:
        path = directory / name
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_title(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def item_records(sessions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for session in sessions:
        session_id = str(session.get("id") or "")
        session_title = str(session.get("title") or "")
        records[session_id] = {
            "id": session_id,
            "kind": "session",
            "title": session_title,
            "date": str(session.get("date") or ""),
            "starts_at": str(session.get("starts_at") or ""),
            "ends_at": str(session.get("ends_at") or ""),
            "location": str(session.get("location") or ""),
            "parent_id": "",
            "parent_title": "",
            "session_number": str(session.get("session_number") or ""),
            "speaker_ids": sorted(map(str, session.get("speaker_ids", []))),
            "description": str(
                session.get("description_html") or session.get("description_text") or ""
            ),
        }
        for presentation in session.get("presentations", []):
            presentation_id = str(presentation.get("id") or "")
            records[presentation_id] = {
                "id": presentation_id,
                "kind": "presentation",
                "title": str(presentation.get("title") or ""),
                "date": str(presentation.get("date") or session.get("date") or ""),
                "starts_at": str(presentation.get("starts_at") or ""),
                "ends_at": str(presentation.get("ends_at") or ""),
                "location": str(presentation.get("location") or ""),
                "parent_id": session_id,
                "parent_title": session_title,
                "session_number": "",
                "speaker_ids": sorted(map(str, presentation.get("speaker_ids", []))),
                "description": str(
                    presentation.get("description_html")
                    or presentation.get("description_text")
                    or ""
                ),
            }
    return records


def referenced_people(sessions: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for session in sessions:
        ids.update(map(str, session.get("speaker_ids", [])))
        ids.update(map(str, session.get("person_ids", [])))
        for presentation in session.get("presentations", []):
            ids.update(map(str, presentation.get("speaker_ids", [])))
            ids.update(map(str, presentation.get("person_ids", [])))
    return ids


def validate_data(directory: Path, expected_dates: set[str] | None = None) -> list[str]:
    """Return structural errors that make a candidate unsafe to promote."""
    errors: list[str] = []
    for name in SOURCE_FILES:
        if not (directory / name).is_file():
            errors.append(f"missing {name}")
    if errors:
        return errors

    try:
        sessions = load_json(directory / "sessions.json")
        people = load_json(directory / "people.json")
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read candidate JSON: {exc}"]
    if not isinstance(sessions, list):
        return ["sessions.json must contain a list"]
    if not isinstance(people, dict):
        return ["people.json must contain an object keyed by person id"]
    if not sessions:
        errors.append("sessions.json is empty")

    all_item_ids: list[str] = []
    dates: set[str] = set()
    for session in sessions:
        session_id = str(session.get("id") or "")
        all_item_ids.append(session_id)
        if not session_id:
            errors.append("session with empty id")
        if not session.get("title"):
            errors.append(f"session {session_id or '<empty>'} has no title")
        if not session.get("date"):
            errors.append(f"session {session_id or '<empty>'} has no date")
        else:
            dates.add(str(session["date"]))
        if session.get("detail_error"):
            errors.append(f"session {session_id} has detail_error")
        if list(map(str, session.get("speaker_ids", []))) != list(
            map(str, session.get("person_ids", []))
        ):
            errors.append(f"session {session_id} speaker_ids differ from person_ids")

        subsession_ids = list(map(str, session.get("subsession_ids", [])))
        presentation_ids = [
            str(presentation.get("id") or "")
            for presentation in session.get("presentations", [])
        ]
        if len(subsession_ids) != len(set(subsession_ids)):
            errors.append(f"session {session_id} has duplicate subsession_ids")
        if set(subsession_ids) != set(presentation_ids):
            errors.append(
                f"session {session_id} subsession_ids differ from presentations"
            )
        for presentation in session.get("presentations", []):
            presentation_id = str(presentation.get("id") or "")
            all_item_ids.append(presentation_id)
            if not presentation_id:
                errors.append(f"session {session_id} has presentation with empty id")
            if not presentation.get("title"):
                errors.append(
                    f"presentation {presentation_id or '<empty>'} has no title"
                )
            if str(presentation.get("parent_id") or "") != session_id:
                errors.append(f"presentation {presentation_id} has wrong parent_id")
            if presentation.get("detail_error"):
                errors.append(f"presentation {presentation_id} has detail_error")
            if list(map(str, presentation.get("speaker_ids", []))) != list(
                map(str, presentation.get("person_ids", []))
            ):
                errors.append(
                    f"presentation {presentation_id} speaker_ids differ from person_ids"
                )
            if (
                "category" not in presentation
                or "category_id" not in presentation
                or presentation.get("category") != session.get("category")
                or presentation.get("category_id") != session.get("category_id")
            ):
                errors.append(
                    f"presentation {presentation_id} category differs from parent"
                )

    duplicates = sorted(
        item_id for item_id, count in Counter(all_item_ids).items() if count > 1
    )
    if duplicates:
        errors.append(f"duplicate item ids: {', '.join(duplicates[:20])}")
    if not dates:
        errors.append("no conference dates found")
    if expected_dates is not None:
        missing_dates = sorted(expected_dates - dates)
        unexpected_dates = sorted(dates - expected_dates)
        if missing_dates:
            errors.append(f"conference dates missing: {', '.join(missing_dates)}")
        if unexpected_dates:
            errors.append(f"unexpected conference dates: {', '.join(unexpected_dates)}")

    wanted_people = referenced_people(sessions)
    actual_people = set(map(str, people))
    missing_people = sorted(wanted_people - actual_people)
    extra_people = sorted(actual_people - wanted_people)
    if missing_people:
        errors.append(
            f"referenced people missing records: {', '.join(missing_people[:20])}"
        )
    if extra_people:
        errors.append(f"unreferenced people records: {', '.join(extra_people[:20])}")
    failed_people = sorted(
        str(person_id)
        for person_id, person in people.items()
        if person.get("detail_error")
    )
    unnamed_people = sorted(
        str(person_id)
        for person_id, person in people.items()
        if not person.get("full_name")
    )
    if failed_people:
        errors.append(f"people with detail_error: {', '.join(failed_people[:20])}")
    if unnamed_people:
        errors.append(f"people without names: {', '.join(unnamed_people[:20])}")
    return errors


COMPARE_FIELDS = (
    "title",
    "date",
    "starts_at",
    "ends_at",
    "location",
    "parent_id",
    "session_number",
    "speaker_ids",
    "description",
)


def changed_fields(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    return [field for field in COMPARE_FIELDS if old[field] != new[field]]


def possible_reuse(old: dict[str, Any], new: dict[str, Any]) -> bool:
    if old["kind"] != new["kind"]:
        return True
    old_title = normalize_title(old["title"])
    new_title = normalize_title(new["title"])
    similarity = SequenceMatcher(None, old_title, new_title).ratio()
    speakers_overlap = bool(set(old["speaker_ids"]) & set(new["speaker_ids"]))
    same_number = bool(
        old["session_number"] and old["session_number"] == new["session_number"]
    )
    return similarity < 0.35 and not speakers_overlap and not same_number


def remap_score(old: dict[str, Any], new: dict[str, Any]) -> int:
    if old["kind"] != new["kind"]:
        return 0
    score = 0
    old_title = normalize_title(old["title"])
    new_title = normalize_title(new["title"])
    if old_title and old_title == new_title:
        score += 70
    if old["session_number"] and old["session_number"] == new["session_number"]:
        score += 85
    old_speakers = set(old["speaker_ids"])
    new_speakers = set(new["speaker_ids"])
    if old_speakers and new_speakers:
        score += round(
            20 * len(old_speakers & new_speakers) / len(old_speakers | new_speakers)
        )
    if old["date"] and old["date"] == new["date"]:
        score += 5
    if old["starts_at"] and old["starts_at"] == new["starts_at"]:
        score += 5
    return score


def suspected_remaps(
    removed: Iterable[dict[str, Any]], added: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_title: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_number: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in added:
        by_title[(item["kind"], normalize_title(item["title"]))].append(item)
        if item["session_number"]:
            by_number[item["session_number"]].append(item)

    matches: list[dict[str, Any]] = []
    for old in removed:
        candidates: dict[str, dict[str, Any]] = {}
        for item in by_title.get((old["kind"], normalize_title(old["title"])), []):
            candidates[item["id"]] = item
        if old["session_number"]:
            for item in by_number.get(old["session_number"], []):
                candidates[item["id"]] = item
        ranked = sorted(
            ((remap_score(old, item), item) for item in candidates.values()),
            key=lambda pair: (-pair[0], pair[1]["id"]),
        )
        if ranked and ranked[0][0] >= 75:
            score, new = ranked[0]
            matches.append(
                {
                    "old_id": old["id"],
                    "new_id": new["id"],
                    "kind": old["kind"],
                    "title": old["title"],
                    "score": score,
                    "ambiguous": len(ranked) > 1 and ranked[1][0] == score,
                }
            )
    return matches


def snapshot_references(snapshot: Any, source: str) -> dict[str, dict[str, int]]:
    try:
        if not isinstance(snapshot["program_version"], str):
            raise TypeError("program_version must be a string")
        if not isinstance(snapshot["exported_at"], str):
            raise TypeError("exported_at must be a string")
        notes = snapshot["notes"]
        rsvps = snapshot["rsvps"]
        if not isinstance(notes, list) or not isinstance(rsvps, list):
            raise TypeError("notes and rsvps must be lists")
    except (KeyError, TypeError) as exc:
        raise ValueError(f"invalid notebook snapshot {source}: {exc}") from exc

    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"notes": 0, "rsvps": 0})
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


def notebook_references(
    snapshot_path: Path | None,
) -> tuple[dict[str, dict[str, int]], list[str]]:
    if snapshot_path is None:
        return {}, ["No notebook snapshot supplied; user-data impact is unknown."]
    try:
        snapshot = load_json(snapshot_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid notebook snapshot {snapshot_path}: {exc}") from exc
    return snapshot_references(snapshot, str(snapshot_path)), []


def fetch_notebook_snapshot(destination: Path) -> Path:
    """Fetch a fresh notebook snapshot through the user's Access session."""
    print(f"Fetching live notebook snapshot from {NOTEBOOK_URL}", flush=True)
    command = [
        "mise",
        "exec",
        "--",
        "cloudflared",
        "access",
        "curl",
        NOTEBOOK_URL,
        "--fail",
        "--silent",
        "--show-error",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "mise is required to run cloudflared; install the tools from mise.toml."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"Could not fetch the live notebook snapshot (exit {exc.returncode})."
        ) from exc

    try:
        snapshot = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Live notebook endpoint returned invalid JSON: {exc}"
        ) from exc
    try:
        snapshot_references(snapshot, NOTEBOOK_URL)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        prefix=f".{destination.name}.",
        dir=destination.parent,
        delete=False,
    ) as tmp:
        tmp.write(content)
        temporary_path = Path(tmp.name)
    os.replace(temporary_path, destination)
    print(f"Saved live notebook snapshot to {destination}", flush=True)
    return destination


def dataset_counts(
    sessions: list[dict[str, Any]], people: dict[str, Any]
) -> dict[str, int]:
    return {
        "sessions": len(sessions),
        "presentations": sum(
            len(session.get("presentations", [])) for session in sessions
        ),
        "people": len(people),
    }


def build_report(
    baseline_dir: Path, candidate_dir: Path, snapshot_path: Path | None = None
) -> dict[str, Any]:
    baseline_sessions = load_json(baseline_dir / "sessions.json")
    baseline_people = load_json(baseline_dir / "people.json")
    baseline_dates = {str(session.get("date") or "") for session in baseline_sessions}
    validation_errors = validate_data(candidate_dir, baseline_dates)
    candidate_sessions = load_json(candidate_dir / "sessions.json")
    candidate_people = load_json(candidate_dir / "people.json")
    old_items = item_records(baseline_sessions)
    new_items = item_records(candidate_sessions)
    old_ids = set(old_items)
    new_ids = set(new_items)
    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    stable_ids = sorted(old_ids & new_ids)

    modified = []
    reused = []
    for item_id in stable_ids:
        fields = changed_fields(old_items[item_id], new_items[item_id])
        if fields:
            modified.append(
                {
                    "id": item_id,
                    "kind": old_items[item_id]["kind"],
                    "title": old_items[item_id]["title"],
                    "fields": fields,
                }
            )
            if possible_reuse(old_items[item_id], new_items[item_id]):
                reused.append(
                    {
                        "id": item_id,
                        "old_kind": old_items[item_id]["kind"],
                        "new_kind": new_items[item_id]["kind"],
                        "old_title": old_items[item_id]["title"],
                        "new_title": new_items[item_id]["title"],
                    }
                )

    references, warnings = notebook_references(snapshot_path)
    orphaned_references = sorted(set(references) - old_ids)
    if orphaned_references:
        warnings.append(
            f"Notebook already references {len(orphaned_references)} id(s) absent from "
            f"the current program: {', '.join(orphaned_references[:20])}"
        )
    removed = [old_items[item_id] for item_id in removed_ids]
    added = [new_items[item_id] for item_id in added_ids]
    remaps = suspected_remaps(removed, added)
    blockers: list[dict[str, Any]] = [
        {"code": "validation_error", "message": error} for error in validation_errors
    ]
    for item_id in removed_ids:
        item_references = references.get(item_id, {"notes": 0, "rsvps": 0})
        if snapshot_path is None or sum(item_references.values()) > 0:
            blockers.append(
                {
                    "code": "removed_id",
                    "item_id": item_id,
                    "kind": old_items[item_id]["kind"],
                    "title": old_items[item_id]["title"],
                    "references": item_references,
                }
            )
    for item in reused:
        blockers.append({"code": "possible_id_reuse", **item})

    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "notebook_snapshot": (
            {"hash": file_hash(snapshot_path)} if snapshot_path is not None else None
        ),
        "baseline": {
            "path": str(baseline_dir.resolve()),
            "hash": content_hash(baseline_dir),
            "counts": dataset_counts(baseline_sessions, baseline_people),
        },
        "candidate": {
            "path": str(candidate_dir.resolve()),
            "hash": content_hash(candidate_dir),
            "counts": dataset_counts(candidate_sessions, candidate_people),
        },
        "summary": {
            "stable_ids": len(stable_ids),
            "added_ids": len(added_ids),
            "removed_ids": len(removed_ids),
            "modified_ids": len(modified),
            "possible_id_reuse": len(reused),
            "suspected_remaps": len(remaps),
        },
        "validation_errors": validation_errors,
        "warnings": warnings,
        "orphaned_notebook_ids": orphaned_references,
        "added": [
            {key: item[key] for key in ("id", "kind", "title", "date", "starts_at")}
            for item in added
        ],
        "removed": [
            {
                **{
                    key: item[key]
                    for key in ("id", "kind", "title", "date", "starts_at")
                },
                "references": references.get(item["id"], {"notes": 0, "rsvps": 0}),
            }
            for item in removed
        ],
        "modified": modified,
        "suspected_remaps": remaps,
        "possible_id_reuse": reused,
        "blockers": blockers,
    }


def render_report(report: dict[str, Any]) -> str:
    baseline = report["baseline"]["counts"]
    candidate = report["candidate"]["counts"]
    summary = report["summary"]
    lines = [
        "# AAIC program refresh report",
        "",
        f"Generated: {report['created_at']}",
        "",
        "| | Current | Candidate |",
        "|---|---:|---:|",
        f"| Sessions | {baseline['sessions']} | {candidate['sessions']} |",
        f"| Presentations | {baseline['presentations']} | {candidate['presentations']} |",
        f"| People | {baseline['people']} | {candidate['people']} |",
        "",
        f"- Stable IDs: {summary['stable_ids']}",
        f"- Added IDs: {summary['added_ids']}",
        f"- Removed IDs: {summary['removed_ids']}",
        f"- Modified stable IDs: {summary['modified_ids']}",
        f"- Suspected remaps: {summary['suspected_remaps']}",
        f"- Possible ID reuse: {summary['possible_id_reuse']}",
        f"- Promotion blockers: {len(report['blockers'])}",
    ]
    for warning in report["warnings"]:
        lines.extend(["", f"> Warning: {warning}"])

    def section(title: str, rows: list[dict[str, Any]], formatter: Any) -> None:
        if not rows:
            return
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {formatter(row)}" for row in rows)

    section(
        "Removed IDs",
        report["removed"],
        lambda row: (
            f"`{row['id']}` ({row['kind']}): {row['title']} "
            f"— {row['references']['rsvps']} RSVP(s), {row['references']['notes']} note(s)"
        ),
    )
    section(
        "Suspected ID remaps (review only)",
        report["suspected_remaps"],
        lambda row: (
            f"`{row['old_id']}` → `{row['new_id']}` ({row['kind']}, score {row['score']})"
            + (" — ambiguous" if row["ambiguous"] else "")
            + f": {row['title']}"
        ),
    )
    section(
        "Possible ID reuse",
        report["possible_id_reuse"],
        lambda row: f"`{row['id']}`: {row['old_title']} → {row['new_title']}",
    )
    section(
        "Added IDs",
        report["added"],
        lambda row: f"`{row['id']}` ({row['kind']}): {row['title']}",
    )
    section(
        "Modified IDs",
        report["modified"],
        lambda row: (
            f"`{row['id']}` ({row['kind']}): {', '.join(row['fields'])} — {row['title']}"
        ),
    )
    section(
        "Validation errors",
        [{"message": e} for e in report["validation_errors"]],
        lambda r: r["message"],
    )
    return "\n".join(lines) + "\n"


def write_report(
    baseline_dir: Path, candidate_dir: Path, snapshot_path: Path | None
) -> dict[str, Any]:
    staged_snapshot = candidate_dir / STAGED_NOTEBOOK
    if snapshot_path is None:
        staged_snapshot.unlink(missing_ok=True)
        report_snapshot = None
    else:
        if snapshot_path.resolve() != staged_snapshot.resolve():
            shutil.copy2(snapshot_path, staged_snapshot)
        report_snapshot = staged_snapshot
    report = build_report(baseline_dir, candidate_dir, report_snapshot)
    (candidate_dir / REPORT_JSON).write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (candidate_dir / REPORT_MD).write_text(render_report(report), encoding="utf-8")
    return report


def print_report_result(candidate_dir: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    print(
        f"Report: {candidate_dir / REPORT_MD}\n"
        f"IDs: {summary['stable_ids']} stable, {summary['added_ids']} added, "
        f"{summary['removed_ids']} removed, {summary['possible_id_reuse']} possible reuse\n"
        f"Promotion blockers: {len(report['blockers'])}\n"
        f"After review: python3 -m scripts.refresh_aaic apply {candidate_dir}"
    )


def require_staging(stage: Path, baseline: Path) -> None:
    if stage.resolve() == baseline.resolve():
        raise SystemExit(
            "Refusing to use the canonical data directory as refresh staging."
        )


def prepare(args: argparse.Namespace) -> None:
    stage = args.stage
    if stage is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        stage = args.refresh_root / stamp
    require_staging(stage, args.baseline)
    if args.notebook_snapshot is not None:
        notebook_references(args.notebook_snapshot)
    if stage.exists() and any(stage.iterdir()) and not args.resume:
        raise SystemExit(f"Stage is not empty: {stage}. Pass --resume to continue it.")
    stage.mkdir(parents=True, exist_ok=True)
    print(f"Staging refresh in {stage}", flush=True)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "scrape_aaic.py"),
        "--outdir",
        str(stage),
        "--people",
        "--detail-workers",
        str(args.detail_workers),
        "--detail-interval",
        str(args.detail_interval),
        "--people-workers",
        str(args.people_workers),
        "--people-interval",
        str(args.people_interval),
        "--save-every",
        str(args.save_every),
    ]
    if args.resume:
        command.append("--resume")
    subprocess.run(command, cwd=ROOT, check=True)
    snapshot_path = args.notebook_snapshot
    if snapshot_path is None:
        snapshot_path = fetch_notebook_snapshot(stage / STAGED_NOTEBOOK)
    report = write_report(args.baseline, stage, snapshot_path)
    print_report_result(stage, report)


def inspect(args: argparse.Namespace) -> None:
    require_staging(args.stage, args.baseline)
    snapshot_path = args.notebook_snapshot
    if snapshot_path is None:
        snapshot_path = fetch_notebook_snapshot(args.stage / STAGED_NOTEBOOK)
    report = write_report(args.baseline, args.stage, snapshot_path)
    print_report_result(args.stage, report)


def unresolved_blockers(
    report: dict[str, Any], allowed_ids: set[str]
) -> list[dict[str, Any]]:
    unresolved = []
    for blocker in report["blockers"]:
        if blocker["code"] in {"removed_id", "possible_id_reuse"}:
            if blocker.get("item_id", blocker.get("id")) in allowed_ids:
                continue
        unresolved.append(blocker)
    return unresolved


def apply(args: argparse.Namespace) -> None:
    require_staging(args.stage, args.baseline)
    report_path = args.stage / REPORT_JSON
    if not report_path.is_file():
        raise SystemExit(f"No {REPORT_JSON} in {args.stage}; run inspect first.")
    report = load_json(report_path)
    if content_hash(args.stage) != report["candidate"]["hash"]:
        raise SystemExit(
            "Candidate files changed after the report was generated; run inspect again."
        )
    if content_hash(args.baseline) != report["baseline"]["hash"]:
        raise SystemExit("Canonical data changed after comparison; run inspect again.")
    staged_snapshot = args.stage / STAGED_NOTEBOOK
    expected_snapshot = report.get("notebook_snapshot")
    if expected_snapshot is None:
        if staged_snapshot.exists():
            raise SystemExit(
                "Notebook snapshot changed after comparison; run inspect again."
            )
    else:
        if (
            not staged_snapshot.is_file()
            or file_hash(staged_snapshot) != expected_snapshot["hash"]
        ):
            raise SystemExit(
                "Notebook snapshot changed after comparison; run inspect again."
            )
    with tempfile.TemporaryDirectory(prefix="aaic-notebook-") as tmp:
        final_snapshot = args.notebook_snapshot
        if final_snapshot is None:
            final_snapshot = fetch_notebook_snapshot(Path(tmp) / STAGED_NOTEBOOK)
        else:
            notebook_references(final_snapshot)
        current_report = build_report(args.baseline, args.stage, final_snapshot)
        blockers = unresolved_blockers(current_report, set(args.allow_id_change))
        if blockers:
            details = "\n".join(
                f"- {blocker['code']}: {blocker.get('item_id') or blocker.get('id') or blocker.get('message')}"
                for blocker in blockers
            )
            raise SystemExit(f"Promotion blocked:\n{details}")

    sessions = load_json(args.stage / "sessions.json")
    people = load_json(args.stage / "people.json")
    with tempfile.TemporaryDirectory(
        prefix="aaic-promote-", dir=args.baseline.parent
    ) as tmp:
        output = Path(tmp)
        write_outputs(sessions, output)
        shutil.copy2(args.stage / "people.json", output / "people.json")
        write_csvs(rows_by_date(sessions, people), output)
        export_sqlite(
            output / "sessions.json",
            output / "people.json",
            output / "aaic_2026.sqlite",
        )
        expected = {
            "sessions.json",
            "sessions.csv",
            "people.json",
            "aaic_2026.sqlite",
            *(path.name for path in output.glob("presentations_*.csv")),
        }
        args.baseline.mkdir(parents=True, exist_ok=True)
        for path in output.iterdir():
            os.replace(path, args.baseline / path.name)
        for stale in args.baseline.glob("presentations_*.csv"):
            if stale.name not in expected:
                stale.unlink()
    print(f"Promoted candidate data to {args.baseline}")
    print(
        "Next: run data integrity tests, then app check/tests and review the Git diff before deploy."
    )


def path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)

    prepare_parser = subcommands.add_parser(
        "prepare", help="run a full scrape into staging"
    )
    prepare_parser.add_argument("--baseline", type=path, default=DEFAULT_DATA)
    prepare_parser.add_argument(
        "--refresh-root", type=path, default=DEFAULT_REFRESH_ROOT
    )
    prepare_parser.add_argument("--stage", type=path)
    prepare_parser.add_argument(
        "--notebook-snapshot",
        type=path,
        help="use a local snapshot instead of fetching through Access",
    )
    prepare_parser.add_argument("--resume", action="store_true")
    prepare_parser.add_argument("--detail-workers", type=int, default=4)
    prepare_parser.add_argument("--detail-interval", type=float, default=0.20)
    prepare_parser.add_argument("--people-workers", type=int, default=4)
    prepare_parser.add_argument("--people-interval", type=float, default=0.05)
    prepare_parser.add_argument("--save-every", type=int, default=100)
    prepare_parser.set_defaults(func=prepare)

    inspect_parser = subcommands.add_parser(
        "inspect", help="validate and compare staged data"
    )
    inspect_parser.add_argument("stage", type=path)
    inspect_parser.add_argument("--baseline", type=path, default=DEFAULT_DATA)
    inspect_parser.add_argument(
        "--notebook-snapshot",
        type=path,
        help="use a local snapshot instead of fetching through Access",
    )
    inspect_parser.set_defaults(func=inspect)

    apply_parser = subcommands.add_parser(
        "apply", help="promote an unchanged reviewed candidate"
    )
    apply_parser.add_argument("stage", type=path)
    apply_parser.add_argument("--baseline", type=path, default=DEFAULT_DATA)
    apply_parser.add_argument(
        "--notebook-snapshot",
        type=path,
        help="use a local snapshot instead of fetching through Access",
    )
    apply_parser.add_argument(
        "--allow-id-change", action="append", default=[], metavar="ID"
    )
    apply_parser.set_defaults(func=apply)
    return result


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
