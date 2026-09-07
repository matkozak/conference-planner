import unittest

from scripts.ctad_2026 import posters_pdf
from scripts.ctad_2026.pdf import lines_from_runs, runs_from_xml
from tests.ctad_2026.fixtures import Text, document


def parse(pages: list[list[Text]]) -> list[posters_pdf.Poster]:
    return posters_pdf.parse_lines(lines_from_runs(runs_from_xml(document(pages))))


def poster_entry(top: int, label: str, title: str, presenter: str) -> list[Text]:
    return [
        Text(top=top, left=68, font="poster-label", text=f"{label} ", width=40),
        Text(top=top, left=112, font="poster-title", text=title),
        Text(top=top + 50, left=68, font="presenter", text=f"Presenter: {presenter}"),
    ]


class PosterStructureTest(unittest.TestCase):
    def test_remote_label_preserves_identity_and_title(self) -> None:
        posters = parse([[Text(top=70, left=68, font="poster-theme", text="IMAGING"),
                          *poster_entry(138, "P33 [Remote]", "Example", "Ada Lovelace")]])
        self.assertEqual(posters[0].label, "P33")
        self.assertEqual(posters[0].title, "Example")
        self.assertTrue(posters[0].remote)

    def test_posters_inherit_the_theme_heading_above_them(self) -> None:
        posters = parse(
            [
                [
                    Text(top=70, left=68, font="poster-theme", text="EPIDEMIOLOGY"),
                    *poster_entry(138, "P33", "First poster", "Ada Lovelace"),
                    *poster_entry(300, "P48", "Second poster", "Alan Turing"),
                    Text(top=500, left=68, font="poster-theme", text="IMAGING"),
                    *poster_entry(560, "P79", "Third poster", "Grace Hopper"),
                ]
            ]
        )

        self.assertEqual([poster.label for poster in posters], ["P33", "P48", "P79"])
        self.assertEqual(
            [poster.theme for poster in posters],
            ["EPIDEMIOLOGY", "EPIDEMIOLOGY", "IMAGING"],
        )
        self.assertEqual(posters[0].presenter, "Ada Lovelace")

    def test_the_contents_page_is_not_mistaken_for_a_theme(self) -> None:
        posters = parse(
            [
                [
                    Text(top=40, left=68, font="day", text="Posters List"),
                    Text(top=70, left=68, font="poster-theme", text="EPIDEMIOLOGY P.3"),
                ],
                [
                    Text(top=70, left=68, font="poster-theme", text="EPIDEMIOLOGY"),
                    *poster_entry(138, "P33", "First poster", "Ada Lovelace"),
                ],
            ]
        )

        self.assertEqual([poster.theme for poster in posters], ["EPIDEMIOLOGY"])

    def test_a_wrapped_title_is_rejoined(self) -> None:
        posters = parse(
            [
                [
                    Text(top=70, left=68, font="poster-theme", text="EPIDEMIOLOGY"),
                    Text(top=138, left=68, font="poster-label", text="P33 ", width=40),
                    Text(top=138, left=112, font="poster-title", text="A very long"),
                    Text(top=160, left=68, font="poster-title", text="poster title"),
                    Text(
                        top=189,
                        left=68,
                        font="presenter",
                        text="Presenter: Ada Lovelace",
                    ),
                ]
            ]
        )

        self.assertEqual(posters[0].title, "A very long poster title")


class PosterAuthorTest(unittest.TestCase):
    def test_standalone_comma_separates_authors(self) -> None:
        posters = parse([[Text(top=70, left=68, font="poster-theme", text="IMAGING"),
                          *poster_entry(138, "P33", "Example", "Ada Lovelace"),
                          Text(top=211, left=68, font="person", text="Ada LOVELACE"),
                          Text(top=212, left=165, font="marker", text="1"),
                          Text(top=211, left=170, font="person", text=", "),
                          Text(top=211, left=180, font="person", text="Alan TURING"),
                          Text(top=212, left=280, font="marker", text="2")]])
        self.assertEqual([a.name for a in posters[0].authors], ["Ada LOVELACE", "Alan TURING"])
        self.assertEqual([a.affiliation_ids for a in posters[0].authors], [[1], [2]])
        self.assertTrue(posters[0].authors[0].presenting)

    def test_authors_bind_to_the_numbered_affiliation_block(self) -> None:
        posters = parse(
            [
                [
                    Text(top=70, left=68, font="poster-theme", text="EPIDEMIOLOGY"),
                    *poster_entry(138, "P33", "A poster", "Ada Lovelace"),
                    Text(top=211, left=68, font="person", text="Ada LOVELACE "),
                    Text(top=212, left=165, font="marker", text="1"),
                    Text(top=211, left=169, font="person", text=" , Alan TURING "),
                    Text(top=212, left=256, font="marker", text="2"),
                    Text(top=227, left=68, font="affiliation-marker", text="1"),
                    Text(
                        top=226, left=71, font="affiliation", text=" Analytical Engine"
                    ),
                    Text(top=227, left=230, font="affiliation-marker", text="2"),
                    Text(top=226, left=232, font="affiliation", text=" Bletchley Park"),
                ]
            ]
        )

        poster = posters[0]
        self.assertEqual(
            [author.name for author in poster.authors], ["Ada LOVELACE", "Alan TURING"]
        )
        self.assertEqual(poster.authors[0].affiliation_ids, [1])
        self.assertEqual(
            poster.affiliations, {1: "Analytical Engine", 2: "Bletchley Park"}
        )

    def test_an_author_list_wrapping_after_a_comma_does_not_merge_names(self) -> None:
        posters = parse(
            [
                [
                    Text(top=70, left=68, font="poster-theme", text="EPIDEMIOLOGY"),
                    *poster_entry(138, "P33", "A poster", "Ada Lovelace"),
                    Text(top=211, left=68, font="person", text="Ramkumar SUBRAMANIAN,"),
                    Text(top=227, left=68, font="person", text="Abdul MOHAMMED"),
                ]
            ]
        )

        self.assertEqual(
            [author.name for author in posters[0].authors],
            ["Ramkumar SUBRAMANIAN", "Abdul MOHAMMED"],
        )


if __name__ == "__main__":
    unittest.main()
