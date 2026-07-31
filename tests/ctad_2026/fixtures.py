"""Synthetic ``pdftohtml -xml`` documents for the CTAD parser tests.

Real CTAD PDFs never enter Git, so the tests drive the parsers from small
hand-written documents in poppler's XML shape.
"""

from dataclasses import dataclass
from xml.sax.saxutils import escape

#: Font ids reused across the fixtures, mirroring the real documents.
FONTS: dict[str, tuple[str, int, str]] = {
    "day": ("ABCDEF+FjallaOne", 32, "#24333a"),
    "keynote": ("ABCDEF+FjallaOne", 18, "#f2762e"),
    "oral": ("ABCDEF+FjallaOne", 18, "#2e7bbe"),
    "symposium": ("ABCDEF+FjallaOne", 18, "#1cb5b3"),
    "heading": ("ABCDEF+FjallaOne", 18, "#000000"),
    "gutter": ("GHIJKL+IBMPlexSansCond", 15, "#000000"),
    "gutter-item": ("GHIJKL+IBMPlexSansCond", 12, "#2e7bbe"),
    "item-label": ("MNOPQR+IBMPlexSansCond", 14, "#2e7bbe"),
    "item-title": ("MNOPQR+IBMPlexSansCond", 15, "#1b3a4b"),
    "person": ("STUVWX+IBMPlexSansCond-Medium", 14, "#24333a"),
    "marker": ("STUVWX+IBMPlexSansCond-Medium", 8, "#24333a"),
    "prose": ("STUVWX+IBMPlexSansCond-Medium", 17, "#000000"),
    "chair": ("YZABCD+IBMPlexSans", 14, "#24333a"),
    "inline-affiliation": ("EFGHIJ+IBMPlexSansCond", 14, "#000000"),
    "affiliation": ("EFGHIJ+IBMPlexSansCond", 9, "#6b7280"),
    "affiliation-marker": ("EFGHIJ+IBMPlexSansCond", 5, "#6b7280"),
    "poster-theme": ("ABCDEF+FjallaOne", 27, "#2e7bbe"),
    "poster-label": ("KLMNOP+IBMPlexSansCond", 18, "#2f8da2"),
    "poster-title": ("KLMNOP+IBMPlexSansCond", 18, "#000000"),
    "presenter": ("KLMNOP+IBMPlexSansCond", 15, "#000000"),
}

BOLD_FONTS = frozenset(
    {
        "item-label",
        "item-title",
        "poster-label",
        "poster-title",
        "presenter",
    }
)
ITALIC_FONTS = frozenset(
    {"inline-affiliation", "affiliation", "affiliation-marker"}
)


@dataclass(frozen=True)
class Text:
    """One positioned text run."""

    top: int
    left: int
    font: str
    text: str
    width: int = 100


def document(pages: list[list[Text]]) -> str:
    """Render pages of runs as a poppler XML document."""
    used: set[str] = set()
    body: list[str] = []
    for number, runs in enumerate(pages, start=1):
        body.append(
            f'<page number="{number}" position="absolute" '
            'top="0" left="0" height="1188" width="918">'
        )
        for run in runs:
            if run.font not in used:
                family, size, color = FONTS[run.font]
                index = list(FONTS).index(run.font)
                body.append(
                    f'<fontspec id="{index}" size="{size}" '
                    f'family="{family}" color="{color}"/>'
                )
                used.add(run.font)
        for run in runs:
            index = list(FONTS).index(run.font)
            content = escape(run.text)
            if run.font in ITALIC_FONTS:
                content = f"<i>{content}</i>"
            if run.font in BOLD_FONTS:
                content = f"<b>{content}</b>"
            body.append(
                f'<text top="{run.top}" left="{run.left}" width="{run.width}" '
                f'height="20" font="{index}">{content}</text>'
            )
        body.append("</page>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<pdf2xml producer="poppler" version="26.01.0">\n'
        + "\n".join(body)
        + "\n</pdf2xml>\n"
    )
