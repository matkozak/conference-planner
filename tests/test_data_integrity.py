from __future__ import annotations

import json
import sqlite3
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "aaic_2026"
SESSIONS_PATH = DATA_DIR / "sessions.json"
PEOPLE_PATH = DATA_DIR / "people.json"
SQLITE_PATH = DATA_DIR / "aaic_2026.sqlite"


def sortable_id(value: str) -> tuple[bool, int | str]:
    return (not value.isdigit(), int(value) if value.isdigit() else value)


class DataIntegrityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sessions = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
        cls.people = json.loads(PEOPLE_PATH.read_text(encoding="utf-8"))

    def test_all_referenced_people_have_records(self) -> None:
        referenced_people: set[str] = set()
        for session in self.sessions:
            referenced_people.update(map(str, session.get("speaker_ids", [])))
            referenced_people.update(map(str, session.get("person_ids", [])))
            for presentation in session.get("presentations", []):
                referenced_people.update(map(str, presentation.get("speaker_ids", [])))
                referenced_people.update(map(str, presentation.get("person_ids", [])))

        people_ids = set(map(str, self.people))
        self.assertEqual([], sorted(referenced_people - people_ids, key=sortable_id))
        self.assertEqual([], sorted(people_ids - referenced_people, key=sortable_id))
        self.assertEqual([], [pid for pid, person in self.people.items() if person.get("detail_error")])
        self.assertEqual([], [pid for pid, person in self.people.items() if not person.get("full_name")])

    def test_subsessions_match_embedded_presentations(self) -> None:
        all_presentation_ids: list[str] = []
        for session in self.sessions:
            session_id = str(session.get("id"))
            subsession_ids = list(map(str, session.get("subsession_ids", [])))
            presentation_ids = [str(item.get("id")) for item in session.get("presentations", [])]
            all_presentation_ids.extend(presentation_ids)

            self.assertEqual(
                set(subsession_ids),
                set(presentation_ids),
                f"{session_id} subsession_ids differ from embedded presentations",
            )
            self.assertEqual(
                len(subsession_ids),
                len(set(subsession_ids)),
                f"{session_id} has duplicate subsession_ids",
            )
            self.assertEqual(
                len(presentation_ids),
                len(set(presentation_ids)),
                f"{session_id} has duplicate embedded presentation ids",
            )
            for presentation in session.get("presentations", []):
                self.assertEqual(
                    session_id,
                    str(presentation.get("parent_id") or ""),
                    f"{presentation.get('id')} has wrong parent_id",
                )

        duplicate_presentation_ids = [
            presentation_id
            for presentation_id, count in Counter(all_presentation_ids).items()
            if count > 1
        ]
        self.assertEqual([], duplicate_presentation_ids)

    def test_sqlite_integrity_matches_json(self) -> None:
        with sqlite3.connect(SQLITE_PATH) as conn:
            self.assertEqual([], conn.execute("PRAGMA foreign_key_check").fetchall())
            self.assertEqual(len(self.sessions), self.count_rows(conn, "sessions"))
            self.assertEqual(
                sum(len(session.get("presentations", [])) for session in self.sessions),
                self.count_rows(conn, "presentations"),
            )
            self.assertEqual(len(self.people), self.count_rows(conn, "people"))
            self.assertEqual(
                [],
                conn.execute(
                    """
                    SELECT person_id FROM session_people
                    WHERE person_id NOT IN (SELECT id FROM people)
                    UNION
                    SELECT person_id FROM presentation_people
                    WHERE person_id NOT IN (SELECT id FROM people)
                    """
                ).fetchall(),
            )
            self.assertEqual(
                [],
                conn.execute(
                    """
                    SELECT id, parent_session_id FROM presentations
                    WHERE parent_session_id NOT IN (SELECT id FROM sessions)
                    """
                ).fetchall(),
            )

    def count_rows(self, conn: sqlite3.Connection, table: str) -> int:
        return int(conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
