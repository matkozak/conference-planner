import unittest

from scripts.ctad_2026.text import (
    is_post_nominal,
    normalize_name,
    normalize_org,
    paragraphs_html,
    titleize,
)


class TitleizeTest(unittest.TestCase):
    def test_all_caps_headings_are_title_cased_with_acronyms_kept(self) -> None:
        self.assertEqual(titleize("ORAL COMMUNICATIONS"), "Oral Communications")
        self.assertEqual(titleize("IMAGING (MRI & PET)"), "Imaging (MRI & PET)")
        self.assertEqual(
            titleize("CLINICAL TRIALS – PHASE IIB & III"),
            "Clinical Trials – Phase IIB & III",
        )
        self.assertEqual(titleize("CTAD WELCOME RECEPTION"), "CTAD Welcome Reception")

    def test_possessive_s_is_lowercase(self) -> None:
        self.assertEqual(
            titleize("INNOVATION IN ALZHEIMER’S THERAPEUTICS"),
            "Innovation In Alzheimer’s Therapeutics",
        )

    def test_mixed_case_titles_are_left_alone(self) -> None:
        title = "Visualizing the Brainshuttle™: Pioneering neuroimaging"

        self.assertEqual(titleize(title), title)

    def test_whitespace_is_collapsed(self) -> None:
        self.assertEqual(
            titleize("Late   Breaking\nSymposium"), "Late Breaking Symposium"
        )


class NameTest(unittest.TestCase):
    def test_an_upper_cased_surname_is_recased(self) -> None:
        self.assertEqual(normalize_name("Nemil BHATT"), "Nemil Bhatt")
        self.assertEqual(normalize_name("Jia Yi LIEW"), "Jia Yi Liew")

    def test_display_cased_names_are_unchanged(self) -> None:
        self.assertEqual(normalize_name("Reisa Sperling"), "Reisa Sperling")
        self.assertEqual(normalize_name("Malú Gámez Tansey"), "Malú Gámez Tansey")

    def test_credentials_are_dropped(self) -> None:
        self.assertEqual(
            normalize_name("Hanan Sheikh Ibrahim, MD, FACP"), "Hanan Sheikh Ibrahim"
        )

    def test_hyphenated_surnames_keep_both_capitals(self) -> None:
        self.assertEqual(normalize_name("Jorge LLIBRE-GUERRA"), "Jorge Llibre-Guerra")
        self.assertEqual(
            normalize_name("Gustavo JIMENEZ-MAGGIORA"), "Gustavo Jimenez-Maggiora"
        )

    def test_a_hyphen_broken_across_a_line_is_rejoined(self) -> None:
        self.assertEqual(normalize_name("Pedro Rosa- Neto"), "Pedro Rosa-Neto")
        self.assertEqual(
            normalize_name("Maria Luisa GORNO- TEMPINI"), "Maria Luisa Gorno-Tempini"
        )

    def test_the_mc_prefix_is_recased_but_mac_is_left_alone(self) -> None:
        self.assertEqual(normalize_name("Scott MCGINNIS"), "Scott McGinnis")
        self.assertEqual(normalize_name("Roisin MCMANUS"), "Roisin McManus")
        # MACHIZAWA is not MacHizawa, so Mac is deliberately not a prefix rule
        self.assertEqual(normalize_name("Sayaka MACHIZAWA"), "Sayaka Machizawa")

    def test_initials_survive(self) -> None:
        self.assertEqual(normalize_name("Gil D. Rabinovici"), "Gil D. Rabinovici")

    def test_credential_only_fragments_are_recognised(self) -> None:
        self.assertTrue(is_post_nominal("MD"))
        self.assertTrue(is_post_nominal("PhD"))
        self.assertFalse(is_post_nominal("Ada Lovelace"))


class OrgTest(unittest.TestCase):
    def test_run_together_country_names_are_separated(self) -> None:
        self.assertEqual(
            normalize_org("Fortrea Inc., Durham,United-States"),
            "Fortrea Inc., Durham, United States",
        )

    def test_stray_separators_are_trimmed(self) -> None:
        self.assertEqual(normalize_org(" - Analytical Engine, "), "Analytical Engine")


class DescriptionTest(unittest.TestCase):
    def test_text_is_escaped_into_paragraphs(self) -> None:
        self.assertEqual(
            paragraphs_html(["Chair: A & B", "", "Second <one>"]),
            "<p>Chair: A &amp; B</p><p>Second &lt;one&gt;</p>",
        )


if __name__ == "__main__":
    unittest.main()
