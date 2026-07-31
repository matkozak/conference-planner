import unittest

from scripts.ctad_2026.pdf import (
    PAGE_HEIGHT,
    Underline,
    apply_underlines,
    lines_from_runs,
    runs_from_xml,
    underlines_from_svg,
)
from tests.ctad_2026.fixtures import Text, document


class RunExtractionTest(unittest.TestCase):
    def test_font_specs_declared_on_one_page_apply_to_later_pages(self) -> None:
        xml = document(
            [
                [Text(top=100, left=200, font="heading", text="First page")],
                [Text(top=100, left=200, font="heading", text="Second page")],
            ]
        )
        runs = runs_from_xml(xml)

        self.assertEqual([run.page for run in runs], [1, 2])
        self.assertEqual({run.font.family for run in runs}, {"FjallaOne"})
        self.assertEqual({run.font.size for run in runs}, {18})

    def test_subset_prefix_is_stripped_from_the_family(self) -> None:
        xml = document([[Text(top=10, left=200, font="person", text="Reisa Sperling")]])

        self.assertEqual(runs_from_xml(xml)[0].font.family, "IBMPlexSansCond-Medium")

    def test_markup_becomes_style_flags_and_blank_runs_are_dropped(self) -> None:
        xml = document(
            [
                [
                    Text(top=10, left=200, font="item-title", text="Bold title"),
                    Text(top=30, left=200, font="affiliation", text="Some university"),
                    Text(top=50, left=200, font="person", text="   "),
                ]
            ]
        )
        runs = runs_from_xml(xml)

        self.assertEqual(len(runs), 2)
        self.assertTrue(runs[0].bold)
        self.assertFalse(runs[0].italic)
        self.assertTrue(runs[1].italic)

    def test_entities_are_decoded(self) -> None:
        xml = document([[Text(top=10, left=200, font="heading", text="A & B")]])

        self.assertEqual(runs_from_xml(xml)[0].text, "A & B")


class LineGroupingTest(unittest.TestCase):
    def test_runs_on_a_shared_baseline_form_one_line_ordered_by_x(self) -> None:
        xml = document(
            [
                [
                    Text(top=102, left=400, font="person", text="second"),
                    Text(top=100, left=200, font="person", text="first"),
                    Text(top=140, left=200, font="person", text="next line"),
                ]
            ]
        )
        lines = lines_from_runs(runs_from_xml(xml))

        self.assertEqual([line.text for line in lines], ["firstsecond", "next line"])
        self.assertEqual(lines[0].top, 100)

    def test_equal_baselines_on_different_pages_stay_separate(self) -> None:
        xml = document(
            [
                [Text(top=100, left=200, font="person", text="page one")],
                [Text(top=100, left=200, font="person", text="page two")],
            ]
        )

        self.assertEqual(len(lines_from_runs(runs_from_xml(xml))), 2)


def svg(paths: str, height: float = 792.0) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="612pt" '
        f'height="{height}pt">{paths}</svg>'
    )


def stroke(width: str, d: str, dx: float, dy: float) -> str:
    return (
        f'<path fill="none" stroke-width="{width}" d="{d}" '
        f'transform="matrix(1, 0, 0, -1, {dx}, {dy})"/>'
    )


class UnderlineExtractionTest(unittest.TestCase):
    def test_a_thin_horizontal_rule_becomes_an_underline(self) -> None:
        found = underlines_from_svg(
            svg(stroke("1", "M 0.0 0.0 L 61.5 0.0", 247.5, 132.5)), 5, PAGE_HEIGHT
        )

        self.assertEqual(len(found), 1)
        mark = found[0]
        self.assertEqual(mark.page, 5)
        # SVG points are scaled into the XML coordinate space (1188 / 792).
        self.assertEqual((mark.left, mark.right, mark.top), (371, 464, 199))

    def test_thick_and_vertical_rules_are_not_underlines(self) -> None:
        paths = (
            # the session accent bar down the left margin
            stroke("2", "M 0.0 0.0 L 0.0 40.5", 37.0, 76.5)
            # a hairline that is too short to be under a name
            + stroke("1", "M 0.0 0.0 L 2.0 0.0", 100.0, 200.0)
            # a sloped segment
            + stroke("1", "M 0.0 0.0 L 60.0 9.0", 100.0, 300.0)
        )

        self.assertEqual(underlines_from_svg(svg(paths), 1, PAGE_HEIGHT), [])


class UnderlineMatchingTest(unittest.TestCase):
    def lines(self):
        document_xml = document(
            [
                [
                    Text(
                        top=182, left=194, font="person", text="Hamid Sohrabi", width=90
                    ),
                    Text(
                        top=182, left=290, font="person", text=", Paul Maruff", width=80
                    ),
                    Text(
                        top=182,
                        left=375,
                        font="person",
                        text=", James D Doecke",
                        width=95,
                    ),
                ]
            ]
        )
        return lines_from_runs(runs_from_xml(document_xml))

    def test_a_rule_marks_only_the_run_above_it(self) -> None:
        lines = self.lines()
        matched = apply_underlines(
            lines, [Underline(page=1, left=378, right=463, top=199)]
        )

        self.assertEqual(matched, 1)
        marked = [run.text for run in lines[0].runs if run.underlined]
        self.assertEqual(marked, [", James D Doecke"])

    def test_a_rule_too_far_below_the_text_matches_nothing(self) -> None:
        lines = self.lines()
        with self.assertLogs("scripts.ctad_2026.pdf", level="WARNING") as logged:
            matched = apply_underlines(
                lines, [Underline(page=1, left=378, right=463, top=260)]
            )

        self.assertEqual(matched, 0)
        self.assertFalse(any(run.underlined for run in lines[0].runs))
        self.assertIn(
            "1 of 1 presenter underlines could not be matched", logged.output[0]
        )


if __name__ == "__main__":
    unittest.main()
