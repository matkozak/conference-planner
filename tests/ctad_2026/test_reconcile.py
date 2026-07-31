import copy
import unittest

from scripts.ctad_2026.reconcile import (
    compare,
    publication_blockers,
    publication_hash,
    render,
)


def program() -> dict[str, object]:
    return {
        "conference": {"id": "ctad-2026"},
        "sessions": [
            {
                "kind": "session",
                "id": "S1",
                "title": "First Symposium",
                "date": "2026-11-16",
                "starts_at": "2026-11-16T09:00:00-05:00",
                "ends_at": "2026-11-16T10:00:00-05:00",
                "location": "Main Hall",
                "presentations": [
                    {
                        "kind": "talk",
                        "id": "S1P1",
                        "title": "A presentation",
                        "speaker_ids": ["p1"],
                    }
                ],
            }
        ],
    }


def snapshot(
    baseline: dict[str, object],
    item_id: str | None = None,
) -> dict[str, object]:
    return {
        "conference_id": "ctad-2026",
        "program_version": publication_hash(baseline),
        "exported_at": "2026-07-31T12:00:00Z",
        "notes": [{"item_id": item_id}] if item_id else [],
        "rsvps": [{"item_id": item_id, "author": "ada@example.com"}]
        if item_id
        else [],
    }


class ReconcileTest(unittest.TestCase):
    def test_unchanged_program_has_no_findings(self) -> None:
        baseline = program()

        result = compare(baseline, copy.deepcopy(baseline), snapshot(baseline))

        self.assertEqual(2, result["summary"]["stable_ids"])
        self.assertEqual(0, result["summary"]["modified_ids"])
        self.assertEqual([], result["items_with_user_content"])

    def test_positional_id_reuse_is_flagged_with_user_content(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["title"] = "Unrelated Closing Ceremony"
        candidate["sessions"][0]["speaker_ids"] = ["p9"]

        result = compare(baseline, candidate, snapshot(baseline, "S1"))

        self.assertEqual(["S1"], [row["id"] for row in result["possible_id_reuse"]])
        self.assertEqual(
            {"notes": 1, "rsvps": 1},
            result["possible_id_reuse"][0]["references"],
        )
        self.assertEqual(1, result["summary"]["items_with_user_content"])

    def test_every_modified_item_carries_reference_counts(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["presentations"][0][
            "title"
        ] = "A presentation, updated"

        result = compare(baseline, candidate, snapshot(baseline, "S1P1"))

        self.assertEqual(1, result["summary"]["modified_ids"])
        self.assertEqual(
            {"notes": 1, "rsvps": 1}, result["modified"][0]["references"]
        )
        self.assertEqual([], result["possible_id_reuse"])

    def test_replacing_a_session_children_is_possible_reuse(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["presentations"][0]["id"] = "OC99"

        result = compare(baseline, candidate, snapshot(baseline, "S1"))

        self.assertEqual(["S1"], [row["id"] for row in result["possible_id_reuse"]])
        self.assertIn("presentation_ids", result["possible_id_reuse"][0]["fields"])

    def test_removed_item_carries_reference_counts(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["presentations"] = []

        result = compare(baseline, candidate, snapshot(baseline, "S1P1"))

        self.assertEqual("S1P1", result["removed"][0]["id"])
        self.assertEqual(
            {"notes": 1, "rsvps": 1}, result["removed"][0]["references"]
        )

    def test_snapshot_must_describe_the_baseline_program(self) -> None:
        baseline = program()
        bad = snapshot(baseline)
        bad["program_version"] = "0" * 64

        with self.assertRaisesRegex(ValueError, "does not match the baseline"):
            compare(baseline, copy.deepcopy(baseline), bad)

    def test_report_calls_out_user_content(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["title"] = "Unrelated Closing Ceremony"

        output = render(compare(baseline, candidate, snapshot(baseline, "S1")))

        self.assertIn("Changed/removed items with user content: 1", output)
        self.assertIn("1 note(s), 1 RSVP(s)", output)

    def test_user_content_change_requires_explicit_acknowledgement(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["presentations"][0][
            "title"
        ] = "A presentation, updated"
        result = compare(baseline, candidate, snapshot(baseline, "S1P1"))

        self.assertEqual(
            ["S1P1: changed item has 1 note(s), 1 RSVP(s)"],
            publication_blockers(result, set()),
        )
        self.assertEqual([], publication_blockers(result, {"S1P1"}))

    def test_possible_reuse_cannot_be_acknowledged_as_a_content_change(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["title"] = "Unrelated Closing Ceremony"
        result = compare(baseline, candidate, snapshot(baseline))

        self.assertEqual(
            ["S1: possible positional ID reuse"],
            publication_blockers(result, {"S1"}),
        )


if __name__ == "__main__":
    unittest.main()
