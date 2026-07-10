from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.refresh_aaic import (
    apply as apply_refresh,
    build_report,
    unresolved_blockers,
    require_staging,
    validate_data,
    write_report,
)


def presentation(item_id: str, title: str, parent_id: str = "S1") -> dict[str, object]:
    return {
        "id": item_id,
        "parent_id": parent_id,
        "date": "2026-07-12",
        "title": title,
        "starts_at": "2026-07-12T09:00:00+01:00",
        "category": "Science",
        "category_id": "1",
        "speaker_ids": ["42"],
        "person_ids": ["42"],
    }


def session(presentations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "S1",
        "date": "2026-07-12",
        "title": "The session",
        "starts_at": "2026-07-12T08:30:00+01:00",
        "category": "Science",
        "category_id": "1",
        "subsession_ids": [item["id"] for item in presentations],
        "presentations": presentations,
    }


def write_data(directory: Path, sessions: list[dict[str, object]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "sessions.json").write_text(json.dumps(sessions), encoding="utf-8")
    people = (
        {"42": {"id": "42", "full_name": "Ada Lovelace"}}
        if any(item.get("presentations") for item in sessions)
        else {}
    )
    (directory / "people.json").write_text(json.dumps(people), encoding="utf-8")


def write_snapshot(path: Path, item_id: str | None = None) -> None:
    notes = []
    rsvps = []
    if item_id:
        notes.append({"item_id": item_id})
        rsvps.append({"item_id": item_id, "author": "ada@example.com"})
    path.write_text(
        json.dumps(
            {
                "program_version": "deadbeef",
                "exported_at": "2026-07-10T12:00:00Z",
                "notes": notes,
                "rsvps": rsvps,
            }
        ),
        encoding="utf-8",
    )


class RefreshReportTest(unittest.TestCase):
    def test_removed_referenced_id_blocks_and_suggests_remap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            snapshot = root / "notebook.json"
            write_data(
                old,
                [session([presentation("P1", "Stable"), presentation("P2", "Moved")])],
            )
            write_data(
                new,
                [session([presentation("P1", "Stable"), presentation("P9", "Moved")])],
            )
            write_snapshot(snapshot, "P2")

            report = build_report(old, new, snapshot)

            self.assertEqual(1, report["summary"]["added_ids"])
            self.assertEqual(1, report["summary"]["removed_ids"])
            self.assertEqual("P2", report["suspected_remaps"][0]["old_id"])
            self.assertEqual("P9", report["suspected_remaps"][0]["new_id"])
            removed = next(item for item in report["removed"] if item["id"] == "P2")
            self.assertEqual({"notes": 1, "rsvps": 1}, removed["references"])
            self.assertIn(
                "removed_id", {blocker["code"] for blocker in report["blockers"]}
            )

    def test_same_id_with_unrelated_identity_is_possible_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            snapshot = root / "notebook.json"
            write_data(old, [session([])])
            changed = session([])
            changed["title"] = "Completely unrelated workshop"
            write_data(new, [changed])
            write_snapshot(snapshot)

            report = build_report(old, new, snapshot)

            self.assertEqual(1, report["summary"]["possible_id_reuse"])
            self.assertEqual("S1", report["possible_id_reuse"][0]["id"])

    def test_missing_snapshot_blocks_unless_explicitly_allowed(self) -> None:
        blockers = [{"code": "notebook_snapshot_missing", "message": "missing"}]
        report = {"blockers": blockers}

        self.assertEqual(blockers, unresolved_blockers(report, set(), False))
        self.assertEqual([], unresolved_blockers(report, set(), True))

    def test_canonical_directory_cannot_be_used_as_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(SystemExit, "canonical data directory"):
                require_staging(Path(tmp), Path(tmp))

    def test_validation_rejects_incomplete_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            bad = presentation("P1", "Broken")
            bad["detail_error"] = "upstream failed"
            write_data(directory, [session([bad])])

            self.assertIn("presentation P1 has detail_error", validate_data(directory))

    def test_report_rejects_changed_conference_date_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "old"
            new = root / "new"
            snapshot = root / "notebook.json"
            write_data(old, [session([])])
            moved = session([])
            moved["date"] = "2026-07-13"
            write_data(new, [moved])
            write_snapshot(snapshot)

            report = build_report(old, new, snapshot)

            self.assertIn(
                "conference dates missing: 2026-07-12", report["validation_errors"]
            )
            self.assertIn(
                "unexpected conference dates: 2026-07-13", report["validation_errors"]
            )

    def test_apply_promotes_unchanged_reviewed_candidate_and_builds_exports(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "current"
            new = root / "candidate"
            snapshot = root / "notebook.json"
            write_data(old, [session([presentation("P1", "Stable")])])
            write_data(new, [session([presentation("P1", "Stable")])])
            write_snapshot(snapshot)
            write_report(old, new, snapshot)

            with contextlib.redirect_stdout(io.StringIO()):
                apply_refresh(
                    argparse.Namespace(
                        stage=new,
                        baseline=old,
                        allow_id_change=[],
                        allow_missing_snapshot=False,
                    )
                )

            self.assertTrue((old / "sessions.csv").is_file())
            self.assertTrue((old / "presentations_2026-07-12.csv").is_file())
            self.assertTrue((old / "aaic_2026.sqlite").is_file())

    def test_apply_recomputes_blockers_instead_of_trusting_edited_report(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "current"
            new = root / "candidate"
            snapshot = root / "notebook.json"
            write_data(
                old,
                [
                    session(
                        [presentation("P1", "Stable"), presentation("P2", "Removed")]
                    )
                ],
            )
            write_data(new, [session([presentation("P1", "Stable")])])
            write_snapshot(snapshot, "P2")
            write_report(old, new, snapshot)
            report_path = new / "report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["blockers"] = []
            report_path.write_text(json.dumps(report), encoding="utf-8")

            with self.assertRaisesRegex(SystemExit, "removed_id"):
                apply_refresh(
                    argparse.Namespace(
                        stage=new,
                        baseline=old,
                        allow_id_change=[],
                        allow_missing_snapshot=False,
                    )
                )


if __name__ == "__main__":
    unittest.main()
