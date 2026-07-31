"""Parse the CTAD 2026 posters PDF into source-shaped records.

The posters document is a flat list grouped under theme headings. It carries no
dates, times, or rooms; those come from the published poster-session schedule in
``schedule.py``. Each entry is a bold ``P<number>`` label and title, a bold
``Presenter:`` line, an author list with superscript affiliation markers, and a
numbered affiliation block.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.ctad_2026.pdf import Line, read_lines
from scripts.ctad_2026.program_pdf import Author, parse_affiliations, parse_authors
from scripts.ctad_2026.text import collapse, fold, normalize_name

POSTER_LABEL = re.compile(r"^P\d+\s*$")
PRESENTER_PREFIX = "Presenter:"
CONTENTS_ENTRY = re.compile(r"P\.\d+\s*$")
#: The theme headings on the contents page and above each group.
HEADING_SIZE = 24
#: The cover title.
COVER_SIZE = 40


@dataclass
class Poster:
    label: str
    theme: str
    title: str
    presenter: str = ""
    authors: list[Author] = field(default_factory=list)
    affiliations: dict[int, str] = field(default_factory=dict)


def parse(pdf: Path) -> list[Poster]:
    """Parse the posters PDF into poster records, in document order."""
    return parse_lines(read_lines(pdf))


def parse_lines(lines: list[Line]) -> list[Poster]:
    """Parse already-extracted poster lines into poster records."""
    posters: list[Poster] = []
    theme = ""
    poster: Poster | None = None
    pending: list[Line] = []
    pending_role = ""

    def flush() -> None:
        nonlocal pending, pending_role
        if poster is not None and pending:
            if pending_role == "affiliation":
                poster.affiliations.update(parse_affiliations(pending))
            else:
                poster.authors.extend(parse_authors(pending))
        pending, pending_role = [], ""

    for line in lines:
        first = line.runs[0]
        text = collapse(line.text)
        if not text or text.upper().startswith("POSTERS"):
            continue

        if first.font.is_display:
            flush()
            if first.size >= COVER_SIZE or CONTENTS_ENTRY.search(text):
                continue
            if first.size >= HEADING_SIZE:
                theme, poster = text, None
            continue

        if poster is None and not (first.bold and POSTER_LABEL.match(first.text)):
            continue

        if first.bold and POSTER_LABEL.match(first.text):
            flush()
            poster = Poster(
                label=first.text.strip(),
                theme=theme,
                title=collapse("".join(run.text for run in line.runs[1:])),
            )
            posters.append(poster)
            pending_role = "title"
            continue

        assert poster is not None
        if first.bold and text.startswith(PRESENTER_PREFIX):
            flush()
            poster.presenter = text[len(PRESENTER_PREFIX) :].strip().rstrip(",")
            pending_role = "presenter"
            continue

        if first.bold and pending_role == "title":
            poster.title = collapse(f"{poster.title} {text}")
            continue

        role = "affiliation" if first.italic else "authors"
        if pending and pending_role != role:
            flush()
        pending.append(line)
        pending_role = role

    flush()
    for poster in posters:
        mark_presenter(poster)
    return posters


def mark_presenter(poster: Poster) -> None:
    """Flag the author the ``Presenter:`` line names.

    The program document underlines its presenter instead; flagging the author
    here lets both documents share one downstream notion of who speaks.
    """
    presenter = fold(normalize_name(poster.presenter))
    if not presenter:
        return
    for author in poster.authors:
        if fold(normalize_name(author.name)) == presenter:
            author.presenting = True
            return
