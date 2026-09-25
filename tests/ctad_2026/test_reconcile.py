import copy
import unittest

from scripts.ctad_2026.reconcile import (
    compare,
    publication_blockers,
    publication_hash,
    reconcile_identities,
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

    def test_content_changes_to_the_same_identity_do_not_block(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["presentations"][0][
            "title"
        ] = "A presentation, updated"
        result = compare(baseline, candidate, snapshot(baseline, "S1P1"))

        self.assertEqual([], publication_blockers(result))

    def test_possible_reuse_only_blocks_when_it_has_user_content(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0]["title"] = "Unrelated Closing Ceremony"
        without_content = compare(baseline, candidate, snapshot(baseline))
        with_content = compare(baseline, candidate, snapshot(baseline, "S1"))

        self.assertEqual([], publication_blockers(without_content))
        self.assertEqual(
            ["S1: possible positional ID reuse"],
            publication_blockers(with_content),
        )

    def test_exact_talk_title_keeps_its_id_when_the_source_code_changes(self) -> None:
        baseline = program()
        candidate = copy.deepcopy(baseline)
        session = candidate["sessions"][0]
        session["id"] = "S9"
        session["title"] = "Renumbered session"
        session["presentations"][0]["id"] = "OC23"
        session["presentations"].append(
            {"kind": "talk", "id": "S1P1", "title": "A new presentation"}
        )

        reconciled, summary = reconcile_identities(baseline, candidate)
        result = reconciled["sessions"][0]

        self.assertEqual("S1", result["id"])
        self.assertEqual("S1P1", result["presentations"][0]["id"])
        self.assertRegex(result["presentations"][1]["id"], r"^t-[a-f0-9]{12}$")
        self.assertEqual(1, summary["matched_presentations"])
        self.assertEqual(1, summary["fresh_presentations"])

    def test_an_empty_placeholder_keeps_its_id_when_its_slot_is_filled(self) -> None:
        baseline = program()
        baseline["sessions"][0]["title"] = "Late Breaking Placeholder"
        baseline["sessions"][0]["presentations"] = []
        candidate = copy.deepcopy(baseline)
        candidate["sessions"][0].update(id="S9", title="Supplied final session")

        reconciled, _ = reconcile_identities(baseline, candidate)

        self.assertEqual("S1", reconciled["sessions"][0]["id"])

    def test_duplicate_titles_keep_matching_source_ids(self) -> None:
        baseline = program()
        baseline["sessions"][0]["presentations"].append(
            {"kind": "talk", "id": "S1P2", "title": "A presentation"}
        )
        candidate = copy.deepcopy(baseline)

        reconciled, _ = reconcile_identities(baseline, candidate)

        self.assertEqual(
            ["S1P1", "S1P2"],
            [item["id"] for item in reconciled["sessions"][0]["presentations"]],
        )


if __name__ == "__main__":
    unittest.main()
