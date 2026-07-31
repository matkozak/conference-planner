"""Conference facts that the CTAD source PDFs do not carry.

The program PDF has no year, venue, or timezone, and the posters PDF has no
schedule at all: it groups posters by theme, and the published poster-session
schedule assigns those themes to days. Both are recorded here so the exporter
stays a pure function of the sources plus this file.
"""

from dataclasses import dataclass

CONFERENCE_ID = "ctad-2026"
CONFERENCE_NAME = "19th Clinical Trials on Alzheimer's Disease"
CONFERENCE_SHORT_NAME = "CTAD 2026"
YEAR = 2026
STARTS_ON = "2026-11-16"
ENDS_ON = "2026-11-19"
TIMEZONE = "America/New_York"

#: CTAD runs one linear program in a single hall, so the source names no rooms.
MAIN_HALL = "Main Hall"
POSTER_HALL = "Poster Hall"


@dataclass(frozen=True)
class PosterSession:
    """A published poster session and the themes displayed in it."""

    number: str
    title: str
    date: str
    starts: str | None
    ends: str | None
    #: Free-text note used where the published span cannot be modelled.
    note: str
    themes: tuple[str, ...]


#: Theme keys are the headings as they appear in the posters PDF.
POSTER_SESSIONS: tuple[PosterSession, ...] = (
    PosterSession(
        number="1",
        title="Poster Session 1",
        date="2026-11-16",
        starts="14:00:00",
        ends=None,
        note=(
            "Runs from Monday, November 16 at 2:00 p.m. through "
            "Tuesday, November 17 at 5:30 p.m."
        ),
        themes=(
            "CLINICAL TRIALS – PHASE IIB & III",
            "CLINICAL TRIALS – PHASE I & IIA",
            "IMAGING (MRI & PET)",
            "ARTIFICIAL INTELLIGENCE-DRIVEN INNOVATION IN ALZHEIMER’S THERAPEUTICS",
            "EPIDEMIOLOGY",
            "NEW HYPOTHESES – NEW THERAPEUTIC APPROACHES FOR AD",
        ),
    ),
    PosterSession(
        number="2",
        title="Poster Session 2",
        date="2026-11-18",
        starts="07:15:00",
        ends="17:30:00",
        note="",
        themes=(
            "NON-PHARMACOLOGIC INTERVENTIONS",
            "BIOMARKERS (CSF & PLASMA)",
            "PRE-CLINICAL, EARLY DISCOVERY AND MECHANISTIC RESEARCH",
        ),
    ),
    PosterSession(
        number="3",
        title="Poster Session 3",
        date="2026-11-19",
        starts="07:15:00",
        ends="17:00:00",
        note="",
        themes=(
            "TRIAL DESIGN, STATISTICAL INNOVATION, AND ANALYTICAL FRAMEWORKS",
            "COGNITIVE AND FUNCTIONAL OUTCOMES",
            "DIGITAL ENDPOINTS, REMOTE MONITORING, AND CONNECTED HEALTH TOOLS",
        ),
    ),
)

#: Poster Session 1 intentionally has no same-day end while multi-day sessions
#: remain outside schema v1. Its published span is preserved in its description.
PERMITTED_OPEN_SESSION_IDS = frozenset({"PS1"})


def session_for_theme(theme: str) -> PosterSession:
    """Return the poster session displaying ``theme``."""
    for session in POSTER_SESSIONS:
        if theme in session.themes:
            return session
    raise KeyError(f"no published poster session covers theme {theme!r}")
