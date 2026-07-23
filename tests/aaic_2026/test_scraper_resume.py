from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.aaic_2026.scrape import (
    attach_presentations,
    fetch_details,
    presentation_work,
)


class PresentationResumeTest(unittest.TestCase):
    def test_resume_only_schedules_missing_presentations(self) -> None:
        complete = {
            "id": "P1",
            "parent_id": "S1",
            "starts_at": "2026-07-12T09:00:00+01:00",
        }
        failed = {"id": "P2", "detail_error": "temporary upstream error"}
        partial = {"id": "P3", "title": "list-only placeholder"}
        rows = [
            {
                "id": "S1",
                "subsession_ids": ["P1", "P2", "P3", "P4"],
                "presentations": [complete, failed, partial],
            }
        ]

        preserved, jobs = presentation_work(rows, resume=True)

        self.assertEqual({"P1": complete}, preserved)
        self.assertEqual([(1, "P2"), (2, "P3"), (3, "P4")], jobs)

    def test_fresh_run_schedules_every_unique_presentation(self) -> None:
        rows = [
            {"subsession_ids": ["P1", "P2"], "presentations": [{"id": "P1"}]},
            {"subsession_ids": ["P2", "P3"]},
        ]

        preserved, jobs = presentation_work(rows, resume=False)

        self.assertEqual({}, preserved)
        self.assertEqual([(1, "P1"), (2, "P2"), (3, "P3")], jobs)

    def test_checkpoint_attaches_preserved_and_new_details_in_parent_order(
        self,
    ) -> None:
        rows = [{"subsession_ids": ["P2", "P1", "pending"]}]
        presentations = {"P1": {"id": "P1"}, "P2": {"id": "P2"}}

        attach_presentations(rows, presentations)

        self.assertEqual([{"id": "P2"}, {"id": "P1"}], rows[0]["presentations"])

    def test_resume_continues_presentations_when_all_parents_are_complete(self) -> None:
        rows = [
            {
                "id": "S1",
                "parent_id": "",
                "subsession_ids": ["P1", "P2"],
                "presentations": [{"id": "P1", "parent_id": "S1"}],
            }
        ]

        def completed_detail(
            idx: int, total: int, item_id: str, _cookie: str, _pacer: object
        ) -> tuple[int, int, str, dict[str, str], float]:
            return idx, total, item_id, {"id": item_id, "parent_id": "S1"}, 0.01

        with (
            tempfile.TemporaryDirectory() as tmp,
            patch(
                "scripts.aaic_2026.scrape.fetch_detail_paced",
                side_effect=completed_detail,
            ) as fetch,
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                fetch_details(
                    rows,
                    cookie="cookie",
                    outdir=Path(tmp),
                    resume=True,
                    workers=1,
                    interval_s=0,
                    save_every=100,
                    log_every=50,
                )

        self.assertEqual(
            ["P1", "P2"], [item["id"] for item in rows[0]["presentations"]]
        )
        self.assertEqual("P2", fetch.call_args.args[2])


if __name__ == "__main__":
    unittest.main()
