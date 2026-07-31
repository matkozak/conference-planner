"""Parse the CTAD 2026 program PDF into source-shaped records.

Layout contract, all of it verifiable from the extracted font metadata:

* the left gutter holds session times at 14-15pt and talk times at 12pt;
* a session begins at each gutter time pair, which makes page breaks irrelevant;
* display-font headings carry the session category in their colour, and the
  session's own title in black;
* bold runs open an item (``OC12``, ``Presentation 2``, ``BIOTECH SHOWCASE 3``);
* author names are 14pt, their affiliation markers 8pt, and the affiliation
  block below is grey italic, so author-to-affiliation binding is read off the
  layout rather than guessed.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.ctad_2026.pdf import Line, Run, read_lines
from scripts.ctad_2026.text import collapse

#: Text to the left of this x-coordinate is the time gutter.
GUTTER_X = 190
#: Text below this y-coordinate is the page footer.
FOOTER_Y = 1100
#: Gutter times closer together than this belong to one start/end pair.
PAIR_GAP = 26
#: A talk's gutter time sits within this many points of its title.
ITEM_TIME_GAP = 14
#: Prose lines further apart than this start a new paragraph.
PARAGRAPH_GAP = 24

TIME = re.compile(r"^(\d{1,2}):(\d{2})\s*([ap])\.m\.?$")
MONTH_DAY = re.compile(r"^([A-Z][a-z]+)\s+(\d{1,2})$")
ITEM_LABEL = re.compile(r"^(OC\s*\d+|Presentation\s*\d+|BIOTECH SHOWCASE\s*\d+)\s*$")
CHAIR_PREFIX = re.compile(r"^(?:Co-)?Chairs?\s*:\s*", re.IGNORECASE)

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

#: Display-heading colour to session category. The source uses one accent per
#: kind of session and black for a session's own title.
CATEGORY_COLORS = {
    "#f2762e": "Keynote",
    "#2e7bbe": "Oral Communications",
    "#1cb5b3": "Symposium",
    "#6dbe45": "Biotech Showcase",
    "#b49bc9": "Late Breaking",
    "#ff6b6b": "Late Breaking Symposium",
    "#ffc107": "Late Breaking Biotech Showcase",
    "#4a0d66": "Social",
}


@dataclass
class Author:
    """A person named in the source, with the affiliations bound to them."""

    name: str
    affiliation_ids: list[int] = field(default_factory=list)
    #: Affiliation typeset inline in italics, used where there is no block.
    affiliation: str = ""
    #: The source underlines the person who actually presents.
    presenting: bool = False


@dataclass
class Item:
    """A talk inside a session."""

    label: str
    title: str
    starts: str | None = None
    authors: list[Author] = field(default_factory=list)
    affiliations: dict[int, str] = field(default_factory=dict)


@dataclass
class Session:
    """A scheduled block of the linear program."""

    date: str
    starts: str | None
    ends: str | None
    category: str | None = None
    label: str | None = None
    title: str = ""
    chair_lines: list[str] = field(default_factory=list)
    description: list[str] = field(default_factory=list)
    authors: list[Author] = field(default_factory=list)
    affiliations: dict[int, str] = field(default_factory=dict)
    items: list[Item] = field(default_factory=list)


def clock(value: str) -> str:
    """``3:05 p.m.`` -> ``15:05:00``."""
    match = TIME.match(value.strip())
    if match is None:
        raise ValueError(f"not a program time: {value!r}")
    hour, minute, meridiem = match.groups()
    return f"{int(hour) % 12 + (12 if meridiem == 'p' else 0):02d}:{minute}:00"


def role_of(run: Run) -> str:
    """Classify a run by its typography."""
    if run.font.is_display:
        return "day" if run.size >= 30 else "heading"
    if run.italic:
        return "affiliation" if run.size <= 9 else "inline-affiliation"
    if run.size <= 9:
        return "marker"
    if run.bold:
        return "title"
    medium = run.font.family.endswith("Medium")
    if (medium and run.size >= 16) or (not medium and run.size >= 14):
        return "prose"
    return "person"


def _block_role(run: Run) -> str:
    role = role_of(run)
    return "person" if role in {"marker", "inline-affiliation"} else role


def split_gutter(
    lines: list[Line],
) -> tuple[list[tuple[int, int, str]], list[tuple[int, int, str]], list[Line]]:
    """Separate gutter times from body text.

    Returns session times, item times, and the body lines with gutter and
    footer runs removed.
    """
    session_times: list[tuple[int, int, str]] = []
    item_times: list[tuple[int, int, str]] = []
    body: list[Line] = []
    for line in lines:
        kept: list[Run] = []
        for run in line.runs:
            if run.top > FOOTER_Y:
                continue
            if run.left >= GUTTER_X:
                kept.append(run)
                continue
            text = run.text.strip()
            if TIME.match(text):
                target = item_times if run.size <= 12 else session_times
                target.append((run.page, run.top, clock(text)))
        if kept:
            line.runs = kept
            line.top = min(run.top for run in kept)
            body.append(line)
    return session_times, item_times, body


@dataclass
class Anchor:
    """A session's gutter time pair, and where it sits on the page."""

    page: int
    top: int
    starts: str
    ends: str | None = None
    last_top: int = 0


def pair_times(times: list[tuple[int, int, str]]) -> list[Anchor]:
    """Group consecutive gutter times into per-session start/end anchors."""
    anchors: list[Anchor] = []
    for page, top, value in times:
        previous = anchors[-1] if anchors else None
        if (
            previous is not None
            and previous.page == page
            and top - previous.last_top <= PAIR_GAP
        ):
            previous.ends = value
            previous.last_top = top
        else:
            anchors.append(Anchor(page=page, top=top, starts=value, last_top=top))
    return anchors


def group_blocks(body: list[Line]) -> list[tuple[str, list[Line]]]:
    """Merge consecutive same-role lines so wrapped text is parsed as a unit.

    Author lists and affiliation blocks always continue across their own line
    breaks. Prose continues only within a paragraph, so that a chair credit and
    the abstract below it do not run together.
    """
    blocks: list[tuple[str, list[Line]]] = []
    for line in body:
        if not line.text:
            continue
        role = _block_role(line.runs[0])
        previous = blocks[-1][1][-1] if blocks and blocks[-1][0] == role else None
        if previous is not None and role in {"person", "affiliation"}:
            blocks[-1][1].append(line)
        elif (
            previous is not None
            and role == "prose"
            and previous.page == line.page
            and line.top - previous.top <= PARAGRAPH_GAP
        ):
            blocks[-1][1].append(line)
        else:
            blocks.append((role, [line]))
    return blocks


def _continues_name(previous: Line) -> bool:
    """True when a name wraps onto the next line rather than ending there."""
    last = previous.runs[-1]
    if role_of(last) in {"marker", "inline-affiliation", "affiliation"}:
        return False
    return not last.text.rstrip().endswith(",")


def parse_authors(lines: list[Line]) -> list[Author]:
    """Read a comma-separated author list with superscript affiliation markers."""
    authors: list[Author] = []
    current: Author | None = None
    for index, line in enumerate(lines):
        if index and not _continues_name(lines[index - 1]):
            # An affiliation that wraps still belongs to the author above it.
            wrapped_affiliation = role_of(line.runs[0]) in {
                "inline-affiliation",
                "affiliation",
            }
            if not wrapped_affiliation:
                current = None
        for run in line.runs:
            role = role_of(run)
            if role == "marker" or run.text.strip().isdigit():
                if current is not None:
                    current.affiliation_ids.extend(
                        int(found) for found in re.findall(r"\d+", run.text)
                    )
                continue
            if role in {"inline-affiliation", "affiliation"}:
                if current is not None:
                    current.affiliation = f"{current.affiliation} {run.text}".strip()
                continue
            for position, part in enumerate(run.text.split(",")):
                part = part.strip()
                if position == 0:
                    if current is None:
                        current = Author(name=part)
                        authors.append(current)
                    elif part:
                        current.name = f"{current.name} {part}".strip()
                elif part:
                    current = Author(name=part)
                    authors.append(current)
            # The rule marks the author this run names, which is the one still
            # open once its comma-separated parts are consumed.
            if current is not None and run.underlined:
                current.presenting = True
    for author in authors:
        author.name = collapse(author.name)
        author.affiliation = collapse(author.affiliation).strip(" ,-")
    return [author for author in authors if author.name]


def parse_affiliations(lines: list[Line]) -> dict[int, str]:
    """Read the numbered affiliation block below an author list."""
    affiliations: dict[int, str] = {}
    key: int | None = None
    buffer: list[str] = []
    for line in lines:
        for run in line.runs:
            if run.size <= 6:
                if key is not None:
                    affiliations[key] = collapse("".join(buffer)).strip(" ,")
                digits = re.sub(r"\D", "", run.text)
                key = int(digits) if digits else 0
                buffer = []
            else:
                buffer.append(run.text)
    if key is not None:
        affiliations[key] = collapse("".join(buffer)).strip(" ,")
    elif buffer:
        affiliations[1] = collapse("".join(buffer)).strip(" ,")
    return affiliations


def parse(pdf: Path, year: int) -> list[Session]:
    """Parse the program PDF into sessions and items."""
    return parse_lines(read_lines(pdf, underlines=True), year)


def parse_lines(lines: list[Line], year: int) -> list[Session]:
    """Parse already-extracted program lines into sessions and items."""
    session_times, item_times, body = split_gutter(lines)
    anchors = pair_times(session_times)

    sessions: list[Session] = []
    date: str | None = None
    session: Session | None = None
    item: Item | None = None
    next_anchor = 0

    for role, lines in group_blocks(body):
        first = lines[0]
        text = collapse(" ".join(line.text for line in lines))

        if role == "day":
            match = MONTH_DAY.match(text)
            if match and match.group(1) in MONTHS:
                month = MONTHS.index(match.group(1)) + 1
                date = f"{year:04d}-{month:02d}-{int(match.group(2)):02d}"
                session = item = None
            continue

        while next_anchor < len(anchors) and (
            anchors[next_anchor].page,
            anchors[next_anchor].top - 12,
        ) <= (first.page, first.top):
            anchor = anchors[next_anchor]
            next_anchor += 1
            if date is None:
                raise ValueError(
                    f"session anchor on page {anchor.page} precedes any day heading"
                )
            session = Session(date=date, starts=anchor.starts, ends=anchor.ends)
            sessions.append(session)
            item = None

        if session is None:
            continue
        target: Session | Item = item if item is not None else session

        if role == "heading":
            category = CATEGORY_COLORS.get(first.runs[0].color)
            if category and session.category is None:
                session.category, session.label = category, text
            elif session.title:
                session.title = f"{session.title} {text}"
            else:
                session.title = text
            continue

        if role == "title":
            label = first.runs[0].text.strip()
            if ITEM_LABEL.match(label) and len(first.runs) > 1:
                item = Item(
                    label=re.sub(r"\s+", "", label),
                    title=collapse("".join(run.text for run in first.runs[1:])),
                    starts=_item_time(item_times, first),
                )
                for extra in lines[1:]:
                    item.title = collapse(f"{item.title} {extra.text}")
                session.items.append(item)
            elif item is not None:
                item.title = collapse(f"{item.title} {text}")
            elif session.title:
                session.description.append(text)
            else:
                session.title = text
            continue

        if role == "affiliation":
            target.affiliations.update(parse_affiliations(lines))
            continue

        if role == "prose":
            if CHAIR_PREFIX.match(text):
                session.chair_lines.append(text)
            elif not session.title and item is None:
                session.title = text
            else:
                session.description.append(text)
            continue

        target.authors.extend(parse_authors(lines))

    return sessions


def _item_time(item_times: list[tuple[int, int, str]], line: Line) -> str | None:
    for page, top, value in item_times:
        if page == line.page and abs(top - line.top) <= ITEM_TIME_GAP:
            return value
    return None
