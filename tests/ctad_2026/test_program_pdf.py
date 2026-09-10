import unittest

from scripts.ctad_2026 import program_pdf
from scripts.ctad_2026.pdf import lines_from_runs, runs_from_xml
from tests.ctad_2026.fixtures import Text, document


def parse(pages: list[list[Text]]) -> list[program_pdf.Session]:
    lines = lines_from_runs(runs_from_xml(document(pages)))
    return program_pdf.parse_lines(lines, 2026)


DAY = [
    Text(top=74, left=193, font="day", text="Monday,"),
    Text(top=106, left=193, font="day", text="November 16"),
]


class ClockTest(unittest.TestCase):
    def test_meridiem_conversion(self) -> None:
        self.assertEqual(program_pdf.clock("3:05 p.m."), "15:05:00")
        self.assertEqual(program_pdf.clock("12:20 p.m."), "12:20:00")
        self.assertEqual(program_pdf.clock("12:05 a.m."), "00:05:00")
        self.assertEqual(program_pdf.clock("7:30 a.m."), "07:30:00")

    def test_non_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            program_pdf.clock("Coffee Break")


class SessionStructureTest(unittest.TestCase):
    def test_text_after_attribution_is_reported_without_extending_the_title(self) -> None:
        parsed = parse([DAY + [
            Text(top=181, left=68, font="gutter", text="9:00 a.m."),
            Text(top=199, left=68, font="gutter", text="10:00 a.m."),
            Text(top=189, left=194, font="oral", text="ORAL COMMUNICATIONS"),
            Text(top=230, left=68, font="gutter-item", text="9:00 a.m."),
            Text(top=230, left=194, font="item-label", text="OC1 "),
            Text(top=230, left=240, font="item-title", text="A wrapped"),
            Text(top=250, left=194, font="item-title", text="title"),
            Text(top=280, left=194, font="person", text="Ada Lovelace"),
            Text(top=300, left=194, font="affiliation", text="1 University"),
            Text(top=335, left=68, font="gutter-item", text="9:10 a.m."),
            Text(top=335, left=194, font="item-title", text="—"),
            Text(top=365, left=194, font="person", text="Unexpected Author"),
            Text(top=400, left=194, font="item-label", text="OC3 "),
            Text(top=400, left=240, font="item-title", text="Next"),
            Text(top=420, left=194, font="item-title", text="talk"),
            Text(top=450, left=194, font="person", text="Grace Hopper"),
            Text(top=480, left=194, font="item-title", text="Unexplained text"),
        ]])

        session = parsed[0]
        self.assertEqual([i.title for i in session.items], ["A wrapped title", "Next talk"])
        self.assertEqual([a.name for a in session.items[0].authors], ["Ada Lovelace"])
        self.assertEqual([f.text for f in session.unconsumed],
                         ["—", "Unexpected Author", "Unexplained text"])
        fragment = session.unconsumed[0]
        self.assertEqual((fragment.after, fragment.page, fragment.top, fragment.starts),
                         ("OC1", 1, 335, "09:10:00"))

    def test_gutter_time_pairs_open_sessions_and_set_their_bounds(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=199, left=68, font="gutter", text="3:15 p.m."),
                    Text(top=189, left=194, font="heading", text="POSTER WALKING TOUR"),
                    Text(top=300, left=68, font="gutter", text="3:15 p.m."),
                    Text(top=318, left=68, font="gutter", text="3:25 p.m."),
                    Text(top=308, left=194, font="keynote", text="KEYNOTE 1"),
                    Text(top=340, left=194, font="heading", text="New Molecules"),
                ]
            ]
        )

        self.assertEqual(len(parsed), 2)
        first, second = parsed
        self.assertEqual((first.starts, first.ends), ("14:15:00", "15:15:00"))
        self.assertEqual(first.title, "POSTER WALKING TOUR")
        self.assertIsNone(first.category)
        self.assertEqual(second.category, "Keynote")
        self.assertEqual(second.label, "KEYNOTE 1")
        self.assertEqual(second.title, "New Molecules")

    def test_a_time_missing_its_final_period_still_sets_the_session_end(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:05 p.m."),
                    Text(top=199, left=68, font="gutter", text="2:40 p.m"),
                    Text(
                        top=189,
                        left=194,
                        font="heading",
                        text="LATE BREAKING COMMUNICATIONS",
                    ),
                ]
            ]
        )

        self.assertEqual((parsed[0].starts, parsed[0].ends), ("14:05:00", "14:40:00"))

    def test_a_session_survives_the_page_break_it_straddles(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=900, left=68, font="gutter", text="3:50 p.m."),
                    Text(top=918, left=68, font="gutter", text="4:50 p.m."),
                    Text(top=908, left=194, font="oral", text="ORAL COMMUNICATIONS"),
                    Text(top=950, left=74, font="gutter-item", text="3:50 p.m."),
                    Text(top=951, left=194, font="item-label", text="OC1 "),
                    Text(top=949, left=223, font="item-title", text="First talk"),
                    Text(top=1130, left=54, font="keynote", text="1"),
                ],
                [
                    Text(top=100, left=74, font="gutter-item", text="4:05 p.m."),
                    Text(top=101, left=194, font="item-label", text="OC2 "),
                    Text(top=99, left=223, font="item-title", text="Second talk"),
                ],
            ]
        )

        self.assertEqual(len(parsed), 1)
        session = parsed[0]
        self.assertEqual([item.label for item in session.items], ["OC1", "OC2"])
        self.assertEqual(
            [item.starts for item in session.items], ["15:50:00", "16:05:00"]
        )

    def test_page_footer_is_discarded(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=189, left=194, font="heading", text="POSTER WALKING TOUR"),
                    Text(top=1130, left=54, font="keynote", text="1"),
                    Text(top=1130, left=798, font="keynote", text="PROGRAM"),
                ]
            ]
        )

        self.assertEqual(parsed[0].title, "POSTER WALKING TOUR")


class AuthorBindingTest(unittest.TestCase):
    def test_ahead_study_superscript_is_not_an_affiliation_marker(self) -> None:
        lines = lines_from_runs(
            runs_from_xml(
                document(
                    [[
                        Text(top=100, left=68, font="affiliation-marker", text="3"),
                        Text(
                            top=99,
                            left=71,
                            font="affiliation",
                            text="Eisai Inc., ",
                        ),
                        Text(top=100, left=220, font="affiliation-marker", text="4"),
                        Text(top=99, left=223, font="affiliation", text="AHEAD "),
                        Text(top=100, left=270, font="affiliation-marker", text="3"),
                        Text(top=99, left=273, font="affiliation", text="-"),
                        Text(top=100, left=280, font="affiliation-marker", text="45"),
                        Text(
                            top=99,
                            left=290,
                            font="affiliation",
                            text=" Study Team",
                        ),
                    ]]
                )
            )
        )

        self.assertEqual(
            program_pdf.parse_affiliations(lines),
            {3: "Eisai Inc.", 4: "AHEAD Study Team"},
        )

    def test_superscript_markers_bind_authors_to_the_affiliation_block(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=189, left=194, font="oral", text="ORAL COMMUNICATIONS"),
                    Text(top=230, left=74, font="gutter-item", text="2:15 p.m."),
                    Text(top=231, left=194, font="item-label", text="OC1 "),
                    Text(top=229, left=223, font="item-title", text="A talk"),
                    Text(top=260, left=194, font="person", text="Ada Lovelace"),
                    Text(top=262, left=280, font="marker", text="1, 2"),
                    Text(top=260, left=300, font="person", text=", Alan Turing"),
                    Text(top=262, left=380, font="marker", text="2"),
                    Text(top=290, left=194, font="affiliation-marker", text="1"),
                    Text(
                        top=289, left=197, font="affiliation", text="Analytical Engine"
                    ),
                    Text(top=290, left=400, font="affiliation-marker", text="2"),
                    Text(top=289, left=403, font="affiliation", text="Bletchley Park"),
                ]
            ]
        )

        item = parsed[0].items[0]
        self.assertEqual(
            [author.name for author in item.authors], ["Ada Lovelace", "Alan Turing"]
        )
        self.assertEqual(item.authors[0].affiliation_ids, [1, 2])
        self.assertEqual(item.authors[1].affiliation_ids, [2])
        self.assertEqual(
            item.affiliations, {1: "Analytical Engine", 2: "Bletchley Park"}
        )

    def test_a_full_size_numeric_run_is_still_an_affiliation_marker(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=189, left=194, font="oral", text="ORAL COMMUNICATIONS"),
                    Text(top=230, left=74, font="gutter-item", text="2:15 p.m."),
                    Text(top=231, left=194, font="item-label", text="OC1 "),
                    Text(top=229, left=223, font="item-title", text="A talk"),
                    Text(top=260, left=194, font="person", text="Giacomo Koch"),
                    Text(top=260, left=280, font="person", text="1"),
                ]
            ]
        )

        author = parsed[0].items[0].authors[0]
        self.assertEqual(author.name, "Giacomo Koch")
        self.assertEqual(author.affiliation_ids, [1])

    def test_a_name_split_across_lines_is_rejoined(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=189, left=194, font="oral", text="ORAL COMMUNICATIONS"),
                    Text(top=230, left=74, font="gutter-item", text="2:15 p.m."),
                    Text(top=231, left=194, font="item-label", text="OC1 "),
                    Text(top=229, left=223, font="item-title", text="A talk"),
                    # "Howard" ends the line without a comma, so it wraps.
                    Text(top=260, left=194, font="person", text="Jane Doe"),
                    Text(top=262, left=280, font="marker", text="1"),
                    Text(top=260, left=300, font="person", text=", Howard"),
                    Text(top=276, left=194, font="person", text="Chertkow"),
                    Text(top=278, left=280, font="marker", text="2"),
                ]
            ]
        )

        item = parsed[0].items[0]
        self.assertEqual(
            [author.name for author in item.authors], ["Jane Doe", "Howard Chertkow"]
        )
        self.assertEqual(item.authors[1].affiliation_ids, [2])

    def test_a_comma_at_the_line_end_starts_a_new_author(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=189, left=194, font="oral", text="ORAL COMMUNICATIONS"),
                    Text(top=230, left=74, font="gutter-item", text="2:15 p.m."),
                    Text(top=231, left=194, font="item-label", text="OC1 "),
                    Text(top=229, left=223, font="item-title", text="A talk"),
                    Text(top=260, left=194, font="person", text="Cynthia Chen"),
                    Text(top=262, left=280, font="marker", text="9"),
                    Text(top=260, left=300, font="person", text=", "),
                    Text(top=276, left=194, font="person", text="Laura Baker"),
                    Text(top=278, left=280, font="marker", text="10"),
                ]
            ]
        )

        item = parsed[0].items[0]
        self.assertEqual(
            [author.name for author in item.authors], ["Cynthia Chen", "Laura Baker"]
        )

    def test_an_inline_affiliation_wrapping_stays_with_its_speaker(self) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=189, left=194, font="keynote", text="KEYNOTE 2"),
                    Text(top=220, left=194, font="heading", text="A Glimpse"),
                    Text(top=260, left=194, font="person", text="Geoffrey Kerchner,"),
                    Text(
                        top=260,
                        left=330,
                        font="inline-affiliation",
                        text=" Roche, Basel",
                    ),
                    Text(
                        top=280,
                        left=194,
                        font="inline-affiliation",
                        text="(Switzerland)",
                    ),
                ]
            ]
        )

        authors = parsed[0].authors
        self.assertEqual([author.name for author in authors], ["Geoffrey Kerchner"])
        self.assertEqual(authors[0].affiliation, "Roche, Basel (Switzerland)")


class PresentingAuthorTest(unittest.TestCase):
    def authors(self, underline: str | None) -> list[program_pdf.Author]:
        pages = [
            DAY
            + [
                Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                Text(top=189, left=194, font="oral", text="ORAL COMMUNICATIONS"),
                Text(top=230, left=74, font="gutter-item", text="2:15 p.m."),
                Text(top=231, left=194, font="item-label", text="OC1 "),
                Text(top=229, left=223, font="item-title", text="A talk"),
                Text(top=260, left=194, font="person", text="Ada Lovelace", width=80),
                Text(top=262, left=276, font="marker", text="1"),
                Text(top=260, left=282, font="person", text=", Alan Turing", width=80),
                Text(top=262, left=364, font="marker", text="2"),
            ]
        ]
        lines = lines_from_runs(runs_from_xml(document(pages)))
        marked = 0
        for line in lines:
            for run in line.runs:
                if underline is not None and run.text == underline:
                    run.underlined = True
                    marked += 1
        if underline is not None:
            assert marked == 1, f"fixture did not mark exactly one run: {marked}"
        return program_pdf.parse_lines(lines, 2026)[0].items[0].authors

    def test_an_underline_on_a_comma_prefixed_run_marks_the_author_it_opens(
        self,
    ) -> None:
        authors = self.authors(", Alan Turing")

        self.assertEqual([a.name for a in authors], ["Ada Lovelace", "Alan Turing"])
        self.assertEqual([a.presenting for a in authors], [False, True])

    def test_no_underline_leaves_every_author_unmarked(self) -> None:
        self.assertEqual([a.presenting for a in self.authors(None)], [False, False])

    def test_an_underline_on_the_first_name_marks_only_that_name(self) -> None:
        self.assertEqual(
            [a.presenting for a in self.authors("Ada Lovelace")], [True, False]
        )


class ProseTest(unittest.TestCase):
    def test_a_wrapped_chair_credit_is_kept_whole_and_apart_from_the_abstract(
        self,
    ) -> None:
        parsed = parse(
            [
                DAY
                + [
                    Text(top=181, left=68, font="gutter", text="2:15 p.m."),
                    Text(top=189, left=194, font="symposium", text="SYMPOSIUM 1"),
                    Text(top=220, left=194, font="heading", text="Visualizing"),
                    Text(
                        top=260,
                        left=194,
                        font="chair",
                        text="Chair: Ada Lovelace, Analytical",
                    ),
                    Text(top=278, left=194, font="chair", text="Engine, London (UK)"),
                    Text(
                        top=340, left=194, font="prose", text="An unrelated paragraph."
                    ),
                ]
            ]
        )

        session = parsed[0]
        self.assertEqual(
            session.chair_lines,
            ["Chair: Ada Lovelace, Analytical Engine, London (UK)"],
        )
        self.assertEqual(session.description, ["An unrelated paragraph."])


if __name__ == "__main__":
    unittest.main()
