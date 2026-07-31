"""Font-tagged text extraction from a PDF, via poppler's ``pdftohtml -xml``.

The CTAD source documents are InDesign exports whose typography encodes the
whole program structure: the left gutter holds times, colour marks the session
category, and superscript affiliation markers are separate text runs at a
smaller size than the author names around them. Extracting plain text throws
all of that away, so the ingestion works on positioned, font-tagged runs.

``extract`` shells out to poppler; ``runs_from_xml`` is pure and is what the
tests exercise.
"""

import logging
import re
import subprocess
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from pathlib import Path

LOGGER = logging.getLogger(__name__)

#: Runs whose baselines are within this many points belong to the same line.
LINE_TOLERANCE = 6
#: Height of a letter page in the coordinate space poppler's XML reports.
PAGE_HEIGHT = 1188


@dataclass(frozen=True)
class Font:
    """A resolved font specification, with poppler's subset prefix removed."""

    family: str
    size: int
    color: str

    @property
    def is_display(self) -> bool:
        """True for the FjallaOne display face used by day and session heads."""
        return self.family == "FjallaOne"


@dataclass
class Run:
    """A positioned run of text sharing one font."""

    page: int
    top: int
    left: int
    width: int
    font: Font
    bold: bool
    italic: bool
    text: str
    #: Set when a rule is drawn beneath this run; see ``read_underlines``.
    underlined: bool = False

    @property
    def size(self) -> int:
        return self.font.size

    @property
    def color(self) -> str:
        return self.font.color


@dataclass
class Line:
    """Runs sharing a baseline, ordered left to right."""

    page: int
    top: int
    runs: list[Run] = field(default_factory=list)

    @property
    def left(self) -> int:
        return self.runs[0].left

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs).strip()


def extract(pdf: Path) -> str:
    """Return poppler's XML rendering of ``pdf``."""
    result = subprocess.run(
        ["pdftohtml", "-i", "-xml", "-stdout", str(pdf)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def runs_from_xml(xml: str) -> list[Run]:
    """Parse ``pdftohtml -xml`` output into positioned runs, in reading order."""
    root = ElementTree.fromstring(xml)
    runs: list[Run] = []
    # Each fontspec is declared once, on the page where it is first used, and
    # stays addressable by id on every later page.
    fonts: dict[str, Font] = {}
    for page_element in root.findall("page"):
        page = int(page_element.get("number", "0"))
        for spec in page_element.findall("fontspec"):
            fonts[spec.get("id", "")] = Font(
                family=(spec.get("family") or "").split("+")[-1],
                size=int(spec.get("size") or 0),
                color=spec.get("color") or "",
            )
        for element in page_element.findall("text"):
            font = fonts.get(element.get("font", ""))
            if font is None:
                continue
            text = "".join(element.itertext())
            if not text.strip():
                continue
            descendants = {child.tag for child in element.iter()}
            runs.append(
                Run(
                    page=page,
                    top=int(element.get("top") or 0),
                    left=int(element.get("left") or 0),
                    width=int(element.get("width") or 0),
                    font=font,
                    bold="b" in descendants,
                    italic="i" in descendants,
                    text=text,
                )
            )
    runs.sort(key=lambda run: (run.page, run.top, run.left))
    return runs


def lines_from_runs(runs: list[Run]) -> list[Line]:
    """Group runs into baseline-aligned lines."""
    lines: list[Line] = []
    for run in runs:
        current = lines[-1] if lines else None
        if (
            current is not None
            and current.page == run.page
            and abs(current.top - run.top) <= LINE_TOLERANCE
        ):
            current.runs.append(run)
        else:
            lines.append(Line(page=run.page, top=run.top, runs=[run]))
    for line in lines:
        line.runs.sort(key=lambda run: run.left)
        line.top = min(run.top for run in line.runs)
    lines.sort(key=lambda line: (line.page, line.top))
    return lines


SVG_PATH = re.compile(r"<path([^>]*)/>")
SVG_SEGMENT = re.compile(
    r'd="M\s*([-\d.]+)\s+([-\d.]+)\s+L\s*([-\d.]+)\s+([-\d.]+)\s*"'
)
SVG_FLIP = re.compile(
    r'transform="matrix\(1,\s*0,\s*0,\s*-1,\s*([-\d.]+),\s*([-\d.]+)\)"'
)
SVG_HEIGHT = re.compile(r'height="([\d.]+)pt"')
#: A rule this thin is an underline; the thicker rules are session accent bars.
UNDERLINE_STROKE = 'stroke-width="1"'
#: An underline sits this far below the top of the run it marks.
UNDERLINE_DROP = (8, 26)


@dataclass(frozen=True)
class Underline:
    """A rule drawn beneath text, in the same space as ``Run`` coordinates."""

    page: int
    left: int
    right: int
    top: int


def underlines_from_svg(svg: str, page: int, height: int) -> list[Underline]:
    """Read thin horizontal rules out of one page of cairo SVG.

    Cairo emits each rule as a single-segment path under a y-flipping matrix,
    so a rule's device position is the transform's offset plus its endpoints.
    """
    page_height = SVG_HEIGHT.search(svg)
    if page_height is None:
        return []
    scale = height / float(page_height.group(1))
    found: list[Underline] = []
    for attributes in SVG_PATH.findall(svg):
        segment = SVG_SEGMENT.search(attributes)
        flip = SVG_FLIP.search(attributes)
        if segment is None or flip is None or UNDERLINE_STROKE not in attributes:
            continue
        x0, y0, x1, y1 = (float(value) for value in segment.groups())
        dx, dy = (float(value) for value in flip.groups())
        if abs(y0 - y1) > 0.5 or abs(x1 - x0) < 4:
            continue
        found.append(
            Underline(
                page=page,
                left=round((dx + min(x0, x1)) * scale),
                right=round((dx + max(x0, x1)) * scale),
                top=round((dy - y0) * scale),
            )
        )
    return found


def read_underlines(pdf: Path, pages: int, height: int) -> list[Underline]:
    """Find the rules the source draws under presenting authors' names.

    An underline is vector art, not a text attribute, so it is absent from the
    XML text layer entirely. Cairo's SVG output keeps it, and is the only
    rendering of the document that exposes it. Cairo writes one page per file,
    hence the per-page invocation.
    """
    found: list[Underline] = []
    for page in range(1, pages + 1):
        svg = subprocess.run(
            ["pdftocairo", "-svg", "-f", str(page), "-l", str(page), str(pdf), "-"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        found.extend(underlines_from_svg(svg, page, height))
    return found


def apply_underlines(lines: list[Line], underlines: list[Underline]) -> int:
    """Flag the run each underline sits beneath. Returns the number matched."""
    runs_by_page: dict[int, list[Run]] = {}
    for line in lines:
        for run in line.runs:
            runs_by_page.setdefault(run.page, []).append(run)

    low, high = UNDERLINE_DROP
    matched = 0
    for mark in underlines:
        best: tuple[int, Run] | None = None
        for run in runs_by_page.get(mark.page, []):
            if run.size < 10 or run.left > mark.right + 3:
                continue
            if run.left + run.width < mark.left - 3:
                continue
            drop = mark.top - run.top
            if low <= drop <= high and (best is None or drop < best[0]):
                best = (drop, run)
        if best is not None:
            best[1].underlined = True
            matched += 1
    if unmatched := len(underlines) - matched:
        LOGGER.warning(
            "%d of %d presenter underlines could not be matched",
            unmatched,
            len(underlines),
        )
    return matched


def read_lines(pdf: Path, underlines: bool = False) -> list[Line]:
    """Extract ``pdf`` and group it into font-tagged lines.

    With ``underlines``, also render the pages as vector art to recover the
    rules drawn under presenting authors, which the text layer omits.
    """
    xml = extract(pdf)
    lines = lines_from_runs(runs_from_xml(xml))
    if underlines and lines:
        pages = max(line.page for line in lines)
        apply_underlines(lines, read_underlines(pdf, pages, PAGE_HEIGHT))
    return lines
