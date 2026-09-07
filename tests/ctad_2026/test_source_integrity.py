"""Checks that run against the real, ignored CTAD sources when present.

These assert structural properties rather than exact counts, so that a refreshed
preliminary program does not break the suite while a parser regression does.
"""

import re
import shutil
import unittest
from typing import Any

from scripts.ctad_2026 import schedule
from scripts.ctad_2026.build import blocking_notes, build, report
from scripts.ctad_2026.paths import SOURCE_DIR


class SourceIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if shutil.which("pdftohtml") is None:
            raise unittest.SkipTest("poppler's pdftohtml is not installed")
        if not (
            list(SOURCE_DIR.glob("program_*.pdf"))
            and list(SOURCE_DIR.glob("posters_*.pdf"))
        ):
            raise unittest.SkipTest(
                f"local CTAD sources are unavailable in {SOURCE_DIR}"
            )
        cls.program, cls.overrides = build()

    def sessions(self, kind: str) -> list[dict[str, Any]]:
        return [s for s in self.program["sessions"] if s["kind"] == kind]

    def test_the_review_report_has_no_actionable_findings(self) -> None:
        notes = report(self.program, self.overrides)
        self.assertEqual(blocking_notes(notes), [])

    def test_keynotes_have_one_presenter_and_keep_the_session_bounds(self) -> None:
        for session in self.sessions("session"):
            if session.get("category") != "Keynote":
                continue
            self.assertEqual(len(session["presentations"]), 1)
            talk = session["presentations"][0]
            self.assertEqual(len(talk["speaker_ids"]), 1)
            self.assertEqual(talk["starts_at"], session["starts_at"])
            self.assertEqual(talk["ends_at"], session["ends_at"])

    def test_every_day_carries_sessions_and_matches_the_conference_range(self) -> None:
        days = self.program["days"]
        self.assertEqual(days, sorted(set(days)))
        self.assertGreaterEqual(days[0], schedule.STARTS_ON)
        self.assertLessEqual(days[-1], schedule.ENDS_ON)
        for day in days:
            self.assertTrue(any(s["date"] == day for s in self.program["sessions"]))

    def test_item_ids_are_unique(self) -> None:
        ids = [s["id"] for s in self.program["sessions"]]
        ids += [p["id"] for s in self.program["sessions"] for p in s["presentations"]]

        self.assertEqual(len(ids), len(set(ids)))

    def test_every_speaker_reference_resolves(self) -> None:
        people = self.program["people"]
        for session in self.program["sessions"]:
            for item in (session, *session["presentations"]):
                for person_id in item.get("speaker_ids", []):
                    self.assertIn(person_id, people)

    def test_the_program_covers_every_poster(self) -> None:
        poster_sessions = self.sessions("poster-session")
        posters = [p for s in poster_sessions for p in s["presentations"]]

        self.assertEqual(len(poster_sessions), len(schedule.POSTER_SESSIONS))
        self.assertTrue(posters)
        self.assertTrue(all(session["presentations"] for session in poster_sessions))

    def test_the_linear_program_runs_forwards_within_each_day(self) -> None:
        by_day: dict[str, list[str]] = {}
        for session in self.sessions("session"):
            if starts := session.get("starts_at"):
                by_day.setdefault(session["date"], []).append(starts)
        for day, starts in by_day.items():
            self.assertEqual(starts, sorted(starts), f"{day} is out of order")

    def test_talks_stay_inside_their_session_window(self) -> None:
        for session in self.sessions("session"):
            start, end = session.get("starts_at"), session.get("ends_at")
            for talk in session["presentations"]:
                if not (talk_start := talk.get("starts_at")):
                    continue
                if start:
                    self.assertGreaterEqual(talk_start, start, talk["id"])
                if end:
                    self.assertLessEqual(talk_start, end, talk["id"])

    def test_every_talk_and_poster_names_at_least_one_speaker(self) -> None:
        for session in self.program["sessions"]:
            for item in session["presentations"]:
                if item["id"] in self.overrides.allowed_missing_presenters:
                    self.assertNotIn("speaker_ids", item)
                    continue
                self.assertGreaterEqual(len(item.get("speaker_ids", [])), 1, item["id"])

    def test_co_authors_are_preserved_as_description_text(self) -> None:
        with_authors = [
            item
            for session in self.program["sessions"]
            for item in session["presentations"]
            if item.get("description_html")
        ]
        presentations = sum(
            item["id"] not in self.overrides.allowed_missing_presenters
            for session in self.program["sessions"]
            for item in session["presentations"]
        )
        self.assertEqual(len(with_authors), presentations)

    def test_every_description_marks_its_speaker_in_bold(self) -> None:
        people = self.program["people"]
        for session in self.program["sessions"]:
            for item in session["presentations"]:
                if item["id"] in self.overrides.allowed_missing_presenters:
                    self.assertNotIn("description_html", item)
                    continue
                speaker = people[item["speaker_ids"][0]]["name"]
                self.assertIn(f"<b>{speaker}</b>", item["description_html"], item["id"])

    def test_descriptions_use_only_allowlisted_bare_tags(self) -> None:
        allowed = {"<b>", "</b>", "<sup>", "</sup>", "<br>", "<p>", "</p>"}
        for session in self.program["sessions"]:
            for item in (session, *session["presentations"]):
                html = item.get("description_html")
                if not html:
                    continue
                self.assertLessEqual(set(re.findall(r"<[^>]+>", html)), allowed)

    def test_no_person_is_a_bare_credential_or_a_fragment(self) -> None:
        for person_id, person in self.program["people"].items():
            self.assertGreater(len(person["name"]), 2, person_id)
            self.assertNotIn(",", person["name"], person_id)


if __name__ == "__main__":
    unittest.main()
