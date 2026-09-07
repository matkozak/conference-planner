import re
import unittest

from scripts.ctad_2026 import schedule
from scripts.ctad_2026.build import (
    Overrides,
    People,
    author_org,
    authors_html,
    blocking_notes,
    build_poster_sessions,
    build_program_sessions,
    item_id,
    report,
    timestamp,
)
from scripts.ctad_2026.posters_pdf import Poster, mark_presenter
from scripts.ctad_2026.program_pdf import Author, Item, Session


def overrides(**kwargs: object) -> Overrides:
    return Overrides(**kwargs)  # type: ignore[arg-type]


class TimestampTest(unittest.TestCase):
    def test_conference_dates_resolve_to_eastern_standard_time(self) -> None:
        self.assertEqual(
            timestamp("2026-11-16", "14:15:00"), "2026-11-16T14:15:00-05:00"
        )

    def test_a_missing_clock_yields_no_timestamp(self) -> None:
        self.assertIsNone(timestamp("2026-11-16", None))


class PeopleTest(unittest.TestCase):
    def test_the_same_name_and_org_reuse_one_id(self) -> None:
        people = People()
        first = people.add("Rachel Buckley", "Mass General Brigham")
        second = people.add("rachel  buckley", "Mass General Brigham")

        self.assertEqual(first, second)
        self.assertEqual(len(people.entries), 1)

    def test_the_same_name_at_a_different_org_is_a_different_person(self) -> None:
        people = People()
        first = people.add("Jane Doe", "Alpha University")
        second = people.add("Jane Doe", "Beta Institute")

        self.assertNotEqual(first, second)

    def test_surnames_are_recased_and_credentials_dropped(self) -> None:
        people = People()
        person_id = people.add("Nemil BHATT, MD", "UTMB, Galveston,United-States")

        assert person_id is not None
        self.assertEqual(people.entries[person_id]["name"], "Nemil Bhatt")
        self.assertEqual(
            people.entries[person_id]["org"], "UTMB, Galveston, United States"
        )

    def test_a_credentials_only_fragment_is_not_a_person(self) -> None:
        self.assertIsNone(People().add("MD"))
        self.assertIsNone(People().add("  "))

    def test_ids_are_stable_across_runs_and_insertion_order(self) -> None:
        first = People()
        first.add("Ada Lovelace", "Analytical Engine")
        first.add("Alan Turing", "Bletchley Park")
        second = People()
        second.add("Alan Turing", "Bletchley Park")
        second.add("Ada Lovelace", "Analytical Engine")

        self.assertEqual(first.as_record(), second.as_record())


class AuthorOrgTest(unittest.TestCase):
    def test_the_first_marker_selects_the_organisation(self) -> None:
        author = Author(name="Ada", affiliation_ids=[2, 1])

        self.assertEqual(
            author_org(author, {1: "Alpha", 2: "Beta"}, overrides()), "Beta"
        )

    def test_a_sole_unnumbered_affiliation_applies_to_every_author(self) -> None:
        author = Author(name="Ada")

        self.assertEqual(
            author_org(author, {1: "Only Place"}, overrides()), "Only Place"
        )

    def test_an_inline_affiliation_is_used_when_there_is_no_block(self) -> None:
        author = Author(name="Ada", affiliation="Analytical Engine")

        self.assertEqual(author_org(author, {}, overrides()), "Analytical Engine")

    def test_a_curated_org_replaces_a_credential_laden_byline(self) -> None:
        curated = overrides(orgs={"MD, Head of Things, Roche": "Roche"})
        author = Author(name="Geoffrey", affiliation="MD, Head of Things, Roche")

        self.assertEqual(author_org(author, {}, curated), "Roche")
        self.assertEqual(curated.used_orgs, {"MD, Head of Things, Roche"})


class AuthorsHtmlTest(unittest.TestCase):
    def authors(self) -> list[Author]:
        return [
            Author(name="Ada Lovelace", affiliation_ids=[1]),
            Author(name="Alan TURING", affiliation_ids=[2, 3]),
        ]

    def test_the_speaker_is_bolded_in_place_not_moved_to_the_front(self) -> None:
        authors = self.authors()

        html = authors_html(authors, {1: "Alpha", 2: "Beta"}, overrides(), [authors[1]])

        self.assertEqual(
            html,
            "Ada Lovelace<sup>1</sup>, <b>Alan Turing</b><sup>2, 3</sup>; "
            "<br><sup>1</sup>Alpha, <sup>2</sup>Beta",
        )

    def test_only_allowlisted_bare_tags_are_emitted(self) -> None:
        authors = self.authors()
        html = authors_html(authors, {1: "A & B <lab>"}, overrides(), [authors[0]])

        self.assertEqual(
            set(re.findall(r"<[^>]+>", html)),
            {"<b>", "</b>", "<sup>", "</sup>", "<br>"},
        )
        self.assertIn("A &amp; B &lt;lab&gt;", html)

    def test_an_inline_affiliation_is_used_when_there_is_no_block(self) -> None:
        authors = [Author(name="Ada Lovelace", affiliation="Analytical Engine")]

        self.assertEqual(
            authors_html(authors, {}, overrides(), [authors[0]]),
            "<b>Ada Lovelace</b>; <br>Analytical Engine",
        )

    def test_no_authors_render_as_nothing(self) -> None:
        self.assertEqual(authors_html([], {}, overrides()), "")


class ItemIdTest(unittest.TestCase):
    def test_labels_map_to_program_unique_ids(self) -> None:
        self.assertEqual(item_id("S4", "OC12"), "OC12")
        self.assertEqual(item_id("S5", "Presentation2"), "S5P2")
        self.assertEqual(item_id("S14", "BIOTECHSHOWCASE3"), "BS3")


class ProgramSessionTest(unittest.TestCase):
    def session(self, **kwargs: object) -> Session:
        defaults: dict[str, object] = {
            "date": "2026-11-16",
            "starts": "09:00:00",
            "ends": "10:00:00",
        }
        return Session(**(defaults | kwargs))  # type: ignore[arg-type]

    def test_a_session_without_its_own_title_falls_back_to_its_category(self) -> None:
        source = [
            self.session(category="Oral Communications", label="ORAL COMMUNICATIONS"),
            self.session(
                starts="11:00:00",
                category="Oral Communications",
                label="ORAL COMMUNICATIONS",
            ),
        ]
        built = build_program_sessions(source, People(), overrides())

        self.assertEqual(
            [session["title"] for session in built],
            ["Oral Communications 1", "Oral Communications 2"],
        )
        self.assertEqual([session["id"] for session in built], ["S1", "S2"])
        self.assertEqual([session["session_number"] for session in built], ["1", "2"])

    def test_a_numbered_label_supplies_the_session_number(self) -> None:
        source = [
            self.session(
                category="Symposium", label="SYMPOSIUM 3", title="Remote Biomarkers"
            )
        ]
        built = build_program_sessions(source, People(), overrides())

        self.assertEqual(built[0]["session_number"], "3")
        self.assertEqual(built[0]["title"], "Remote Biomarkers")

    def test_a_curated_chair_becomes_a_speaker_and_a_description(self) -> None:
        curated = overrides(
            chairs={
                "Chair: Ada Lovelace, Analytical Engine": [
                    {"name": "Ada Lovelace", "org": "Analytical Engine"}
                ]
            }
        )
        source = [
            self.session(
                category="Symposium",
                label="SYMPOSIUM 1",
                title="A symposium",
                chair_lines=["Chair: Ada Lovelace, Analytical Engine"],
            )
        ]
        people = People()
        built = build_program_sessions(source, people, curated)

        self.assertIn("<p>Chair: Ada Lovelace</p>", built[0]["description_html"])
        speaker = built[0]["speaker_ids"][0]
        self.assertEqual(people.entries[speaker]["name"], "Ada Lovelace")

    def test_an_uncurated_chair_line_is_left_out_rather_than_guessed(self) -> None:
        source = [
            self.session(
                category="Symposium",
                label="SYMPOSIUM 1",
                title="A symposium",
                chair_lines=["Chair: Someone New, Somewhere"],
            )
        ]
        built = build_program_sessions(source, People(), overrides())

        self.assertNotIn("speaker_ids", built[0])

    def test_talks_carry_their_own_start_time_and_speakers(self) -> None:
        item = Item(
            label="OC1",
            title="A talk",
            starts="09:15:00",
            authors=[Author(name="Ada Lovelace", affiliation_ids=[1])],
            affiliations={1: "Analytical Engine"},
        )
        source = [
            self.session(
                category="Oral Communications",
                label="ORAL COMMUNICATIONS",
                items=[item],
            )
        ]
        built = build_program_sessions(source, People(), overrides())
        talk = built[0]["presentations"][0]

        self.assertEqual(talk["kind"], "talk")
        self.assertEqual(talk["id"], "OC1")
        self.assertEqual(talk["starts_at"], "2026-11-16T09:15:00-05:00")
        self.assertEqual(talk["location"], schedule.MAIN_HALL)
        self.assertEqual(len(talk["speaker_ids"]), 1)
        self.assertIn("<b>Ada Lovelace</b>", talk["description_html"])

    def test_every_underlined_author_becomes_a_speaker(self) -> None:
        item = Item(
            label="Presentation1",
            title="A roundtable",
            authors=[
                Author(name="Ada Lovelace", presenting=True),
                Author(name="Charles Babbage"),
                Author(name="Alan Turing", presenting=True),
            ],
        )
        people = People()
        built = build_program_sessions(
            [self.session(title="A session", items=[item])], people, overrides()
        )
        talk = built[0]["presentations"][0]

        self.assertEqual(
            [people.entries[person_id]["name"] for person_id in talk["speaker_ids"]],
            ["Ada Lovelace", "Alan Turing"],
        )
        self.assertIn("<b>Ada Lovelace</b>", talk["description_html"])
        self.assertIn("Charles Babbage", talk["description_html"])
        self.assertNotIn("<b>Charles Babbage</b>", talk["description_html"])
        self.assertIn("<b>Alan Turing</b>", talk["description_html"])

    def test_multiple_unmarked_authors_remain_ambiguous(self) -> None:
        item = Item(
            label="Presentation1",
            title="An ambiguous talk",
            authors=[Author(name="Ada Lovelace"), Author(name="Alan Turing")],
        )
        people = People()
        built = build_program_sessions(
            [self.session(title="A session", items=[item])], people, overrides()
        )
        talk = built[0]["presentations"][0]

        self.assertNotIn("speaker_ids", talk)
        self.assertTrue(
            any(
                "no presenting author resolved" in note
                for note in report(
                    {"sessions": built, "people": people.as_record()}, overrides()
                )
            )
        )

    def test_an_introducer_prefix_is_not_part_of_the_name(self) -> None:
        source = [
            self.session(
                category="Keynote",
                label="KEYNOTE 1",
                title="A keynote",
                authors=[Author(name="Introduction: Bruno Vellas", affiliation="IHU")],
            )
        ]
        people = People()
        build_program_sessions(source, people, overrides())

        self.assertEqual(
            [person["name"] for person in people.entries.values()], ["Bruno Vellas"]
        )


class PosterSessionTest(unittest.TestCase):
    def poster(self, label: str, theme: str) -> Poster:
        return self.marked(
            Poster(
                label=label,
                theme=theme,
                title="A poster",
                presenter="Ada Lovelace",
                authors=[Author(name="Ada LOVELACE", affiliation_ids=[1])],
                affiliations={1: "Analytical Engine"},
            )
        )

    def marked(self, poster: Poster) -> Poster:
        """Apply the parser's presenter marking, as the real pipeline does."""
        mark_presenter(poster)
        return poster

    def test_posters_land_in_the_published_session_for_their_theme(self) -> None:
        posters = [
            self.poster("P1", "EPIDEMIOLOGY"),
            self.poster("P2", "BIOMARKERS (CSF & PLASMA)"),
            self.poster("P3", "COGNITIVE AND FUNCTIONAL OUTCOMES"),
        ]
        built = build_poster_sessions(posters, People(), overrides())

        self.assertEqual([session["id"] for session in built], ["PS1", "PS2", "PS3"])
        self.assertEqual(
            [[item["id"] for item in session["presentations"]] for session in built],
            [["P1"], ["P2"], ["P3"]],
        )
        self.assertEqual(
            [session["date"] for session in built],
            [
                "2026-11-16",
                "2026-11-18",
                "2026-11-19",
            ],
        )
        self.assertEqual(built[0]["kind"], "poster-session")
        self.assertEqual(built[0]["presentations"][0]["kind"], "poster")
        self.assertEqual(
            built[0]["ends_at"], "2026-11-17T17:30:00-05:00"
        )

    def test_an_unknown_theme_fails_loudly(self) -> None:
        with self.assertRaises(KeyError):
            build_poster_sessions(
                [self.poster("P1", "A BRAND NEW THEME")], People(), overrides()
            )

    def test_the_named_presenter_is_the_only_speaker(self) -> None:
        poster = self.poster("P1", "EPIDEMIOLOGY")
        poster.authors.insert(0, Author(name="Alan TURING", affiliation_ids=[1]))
        people = People()
        built = build_poster_sessions([poster], people, overrides())
        item = built[0]["presentations"][0]

        self.assertEqual(len(item["speaker_ids"]), 1)
        self.assertEqual(people.entries[item["speaker_ids"][0]]["name"], "Ada Lovelace")
        # the co-author is kept as display text, the presenter marked in bold
        self.assertIn("Alan Turing", item["description_html"])
        self.assertIn("<b>Ada Lovelace</b>", item["description_html"])
        self.assertEqual([p["name"] for p in people.entries.values()], ["Ada Lovelace"])


class GlyphRepairTest(unittest.TestCase):
    def setUp(self) -> None:
        self.overrides = Overrides.load()

    def test_the_lost_glyphs_are_restored(self) -> None:
        self.assertEqual(self.overrides.repair("Plasma A?42"), "Plasma Aβ42")
        self.assertEqual(self.overrides.repair("non-A? peptides"), "non-Aβ peptides")
        self.assertEqual(self.overrides.repair("APOE ?4 carriers"), "APOE ε4 carriers")
        self.assertEqual(
            self.overrides.repair("Novel ?-Synuclein"), "Novel α-Synuclein"
        )
        self.assertEqual(self.overrides.repair("Double?Blind"), "Double-Blind")
        self.assertEqual(self.overrides.repair("TML?6"), "TML-6")

    def test_real_question_marks_survive(self) -> None:
        sentence = "Preventing Dementia with Shingles Vaccination? Evidence from Trials"

        self.assertEqual(self.overrides.repair(sentence), sentence)


class ReportTest(unittest.TestCase):
    def program(self, title: str) -> dict[str, object]:
        return {
            "sessions": [
                {
                    "kind": "poster-session",
                    "id": "S1",
                    "title": "A session",
                    "date": "2026-11-16",
                    "starts_at": "2026-11-16T09:00:00-05:00",
                    "ends_at": "2026-11-16T10:00:00-05:00",
                    "presentations": [
                        {
                            "kind": "poster",
                            "id": "P1",
                            "title": title,
                            "speaker_ids": ["p1"],
                        }
                    ],
                }
            ],
            "people": {},
        }

    def test_a_leftover_glyph_is_reported(self) -> None:
        notes = report(self.program("Plasma A? levels"), overrides())

        self.assertTrue(any("unmapped glyph in P1" in note for note in notes))

    def test_sentence_punctuation_is_not_reported(self) -> None:
        self.assertEqual(
            report(self.program("Does it work? Evidence"), overrides()), []
        )

    def test_an_override_the_source_no_longer_contains_is_reported(self) -> None:
        stale = overrides(chairs={"Chair: Gone Away": []})

        notes = report(self.program("A title"), stale)

        self.assertTrue(any("unused chair override" in note for note in notes))

    def test_a_digit_in_a_person_name_is_reported(self) -> None:
        program = self.program("A title")
        program["people"] = {"p1": {"name": "Giacomo Koch 1"}}

        notes = report(program, overrides())

        self.assertTrue(any("digit in person name p1" in note for note in notes))

    def test_an_unmapped_glyph_in_a_description_is_reported(self) -> None:
        program = self.program("A title")
        program["sessions"][0]["presentations"][0][
            "description_html"
        ] = "Plasma A? levels"

        notes = report(program, overrides())

        self.assertTrue(any("P1 description" in note for note in notes))

    def test_missing_bounds_and_empty_sessions_are_reported(self) -> None:
        program = self.program("A title")
        session = program["sessions"][0]
        session["presentations"] = []
        del session["ends_at"]

        notes = report(program, overrides())

        self.assertTrue(any("empty session S1" in note for note in notes))
        self.assertTrue(any("missing session bound in S1" in note for note in notes))

    def test_an_uncurated_chair_line_is_reported(self) -> None:
        state = overrides()
        state.chair_people("Chair: Needs review")

        notes = report(self.program("A title"), state)

        self.assertTrue(any("uncurated chair line" in note for note in notes))

    def test_a_presenter_without_one_author_match_is_reported(self) -> None:
        state = overrides()
        state.unmatched_presenters.add("P1: Ambiguous Person")

        notes = report(self.program("A title"), state)

        self.assertTrue(
            any("presenter does not match exactly one author" in note for note in notes)
        )

    def test_empty_sessions_are_informational_but_other_findings_block(self) -> None:
        notes = [
            "empty session S1: Placeholder",
            "uncurated chair line: Chair: Needs review",
        ]

        self.assertEqual([notes[1]], blocking_notes(notes))


class OverridesFileTest(unittest.TestCase):
    def test_every_pattern_compiles_and_every_chair_entry_is_shaped(self) -> None:
        loaded = Overrides.load()

        self.assertTrue(loaded.glyph_repairs)
        for pattern, _replacement in loaded.glyph_repairs:
            self.assertIsInstance(pattern, re.Pattern)
        for line, people in loaded.chairs.items():
            self.assertTrue(line.strip())
            for person in people:
                self.assertIn("name", person)


if __name__ == "__main__":
    unittest.main()
