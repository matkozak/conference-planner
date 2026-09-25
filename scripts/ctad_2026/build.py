#!/usr/bin/env python3
"""Build the CTAD 2026 ConferenceProgram publication candidate.

CTAD has no structured provider, so this exporter targets the application's
program contract directly rather than emitting a provider dump for an adapter.
The output is validated by the app before publication.
"""

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.ctad_2026 import posters_pdf, program_pdf, schedule
from scripts.ctad_2026.paths import OVERRIDES_FILE, PROGRAM_CANDIDATE, SOURCE_DIR
from scripts.ctad_2026.program_pdf import Author, Item, Session
from scripts.ctad_2026.text import (
    collapse,
    fold,
    is_post_nominal,
    normalize_name,
    normalize_org,
    paragraphs_html,
    titleize,
)

SCHEMA_VERSION = 1
INTRODUCTION_PREFIX = re.compile(r"^Introduction\s*:\s*", re.IGNORECASE)
BIOTECH_LABEL = re.compile(r"^BIOTECHSHOWCASE(\d+)$")
PRESENTATION_LABEL = re.compile(r"^Presentation(\d+)$")
LATE_BREAKING_SYMPOSIUM_LABEL = re.compile(r"^LATEBREAKINGSYMPOSIUM(\d+)$")
#: A question mark that is not sentence punctuation is a glyph the PDF lost.
UNMAPPED_GLYPH = re.compile(r"\?(?!$|\s+[A-Z(])")
DIGIT_IN_NAME = re.compile(r"\d")
INFORMATIONAL_REVIEW_PREFIXES = ("awaiting presentation details ",)
STANDALONE_EVENT = re.compile(
    r"^(?:coffee break\b|lunch\b|poster walking tour\b|welcome ceremony\b)",
    re.IGNORECASE,
)
PROGRAM_END = re.compile(r"^end of the conference(?: day)?$", re.IGNORECASE)


@dataclass
class Overrides:
    """Curated corrections layered onto the deterministic parse."""

    glyph_repairs: list[tuple[re.Pattern[str], str]] = field(default_factory=list)
    chairs: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    orgs: dict[str, str] = field(default_factory=dict)
    sessions: list[dict[str, Any]] = field(default_factory=list)
    item_times: list[dict[str, Any]] = field(default_factory=list)
    insertions: list[dict[str, Any]] = field(default_factory=list)
    posters: dict[str, dict[str, Any]] = field(default_factory=dict)
    unconsumed: list[str] = field(default_factory=list)
    allowed_missing_presenters: set[str] = field(default_factory=set)
    used_chairs: set[str] = field(default_factory=set)
    used_names: set[str] = field(default_factory=set)
    used_orgs: set[str] = field(default_factory=set)
    uncurated_chairs: set[str] = field(default_factory=set)
    unmatched_presenters: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: Path = OVERRIDES_FILE) -> Overrides:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            glyph_repairs=[
                (re.compile(entry["pattern"]), entry["replacement"])
                for entry in raw.get("glyph_repairs", [])
            ],
            chairs=raw.get("chairs", {}),
            names={
                key: value
                for key, value in raw.get("names", {}).items()
                if not key.startswith("_")
            },
            orgs=raw.get("orgs", {}),
            sessions=raw.get("sessions", []),
            item_times=raw.get("item_times", []),
            insertions=raw.get("insertions", []),
            posters=raw.get("posters", {}),
        )

    def repair(self, text: str) -> str:
        """Substitute glyphs the posters PDF failed to map to Unicode."""
        for pattern, replacement in self.glyph_repairs:
            text = pattern.sub(replacement, text)
        return text

    def name(self, display: str) -> str:
        """Correct a name the source itself prints wrongly."""
        curated = self.names.get(display)
        if curated is None:
            return display
        self.used_names.add(display)
        return curated

    def org(self, affiliation: str) -> str:
        curated = self.orgs.get(affiliation)
        if curated is None:
            return affiliation
        self.used_orgs.add(affiliation)
        return curated

    def chair_people(self, line: str) -> list[dict[str, str]] | None:
        curated = self.chairs.get(line)
        if curated is None:
            self.uncurated_chairs.add(line)
            return None
        self.used_chairs.add(line)
        return curated


class People:
    """Person store keyed on normalised name and organisation."""

    def __init__(self, overrides: "Overrides | None" = None) -> None:
        self.entries: dict[str, dict[str, str]] = {}
        self._ids: dict[tuple[str, str], str] = {}
        self._overrides = overrides or Overrides()

    def add(self, name: str, org: str = "") -> str | None:
        """Register a person and return their id, or None if unusable."""
        display = self._overrides.name(normalize_name(name))
        if not display or is_post_nominal(name):
            return None
        org = normalize_org(org)
        key = (fold(display), fold(org))
        existing = self._ids.get(key)
        if existing is not None:
            return existing
        digest = hashlib.sha1(f"{key[0]}|{key[1]}".encode()).hexdigest()[:10]
        person_id = f"p{digest}"
        self._ids[key] = person_id
        self.entries[person_id] = {"name": display} | ({"org": org} if org else {})
        return person_id

    def as_record(self) -> dict[str, dict[str, str]]:
        return dict(sorted(self.entries.items()))


def timestamp(date: str, clock: str | None) -> str | None:
    """Combine a conference date and wall clock into an offset timestamp."""
    if clock is None:
        return None
    moment = datetime.fromisoformat(f"{date}T{clock}").replace(
        tzinfo=ZoneInfo(schedule.TIMEZONE)
    )
    return moment.isoformat()


def author_org(
    author: Author, affiliations: dict[int, str], overrides: Overrides
) -> str:
    """Resolve an author's organisation from their affiliation markers."""
    for marker in author.affiliation_ids:
        resolved = affiliations.get(marker)
        if resolved:
            return overrides.org(collapse(resolved))
    if author.affiliation:
        return overrides.org(collapse(author.affiliation))
    if not author.affiliation_ids and len(affiliations) == 1:
        return overrides.org(next(iter(affiliations.values())))
    return ""


def speaker_ids(
    authors: list[Author],
    affiliations: dict[int, str],
    people: People,
    overrides: Overrides,
) -> list[str]:
    """Register authors and return their deduplicated ids in source order."""
    ids: list[str] = []
    for author in authors:
        name = INTRODUCTION_PREFIX.sub("", author.name)
        person_id = people.add(name, author_org(author, affiliations, overrides))
        if person_id is not None and person_id not in ids:
            ids.append(person_id)
    return ids


def item_id(session_id: str, label: str) -> str:
    """Map a source item label onto a program-unique id."""
    if label.startswith("Uncoded"):
        return f"{session_id}T{label.removeprefix('Uncoded')}"
    if match := BIOTECH_LABEL.match(label):
        return f"BS{match.group(1)}"
    if match := PRESENTATION_LABEL.match(label):
        return f"{session_id}P{match.group(1)}"
    if match := LATE_BREAKING_SYMPOSIUM_LABEL.match(label):
        return f"LBS{match.group(1)}"
    return label


def session_title(session: Session) -> str:
    """A session's own title, or its category heading when it has none."""
    if session.title:
        return titleize(session.title)
    if session.label:
        return titleize(session.label)
    return "Session"


def presenting_authors(authors: list[Author]) -> list[Author]:
    """Return every underlined author, or the sole author when unmarked."""
    marked = [author for author in authors if author.presenting]
    if marked:
        return marked
    return authors if len(authors) == 1 else []


def authors_html(
    authors: list[Author],
    affiliations: dict[int, str],
    overrides: Overrides,
    speakers: list[Author] | None = None,
) -> str:
    """Render authors in source order and their affiliations as safe HTML."""
    if not authors:
        return ""
    names: list[str] = []
    for author in authors:
        name = escape(overrides.name(normalize_name(author.name)))
        if speakers and any(author is speaker for speaker in speakers):
            name = f"<b>{name}</b>"
        markers = ", ".join(str(marker) for marker in author.affiliation_ids)
        names.append(f"{name}<sup>{markers}</sup>" if markers else name)
    flow = ", ".join(names)

    if affiliations:
        block = ", ".join(
            f"<sup>{marker}</sup>{escape(normalize_org(overrides.org(text)))}"
            for marker, text in sorted(affiliations.items())
        )
    elif authors[0].affiliation:
        block = escape(normalize_org(overrides.org(authors[0].affiliation)))
    else:
        return flow
    return f"{flow}; <br>{block}"


def build_talk(
    session_id: str,
    session: Session,
    item: Item,
    people: People,
    overrides: Overrides,
) -> dict[str, Any]:
    talk: dict[str, Any] = {
        "kind": "talk",
        "id": item_id(session_id, item.label),
        "title": overrides.repair(collapse(item.title)),
        "location": schedule.MAIN_HALL,
    }
    starts = timestamp(session.date, item.starts)
    if starts:
        talk["starts_at"] = starts
    if ends := timestamp(session.date, item.ends):
        talk["ends_at"] = ends
    speakers = presenting_authors(item.authors)
    ids = speaker_ids(speakers, item.affiliations, people, overrides)
    if ids:
        talk["speaker_ids"] = ids
    description = authors_html(item.authors, item.affiliations, overrides, speakers)
    if description:
        talk["description_html"] = description
    return talk


def prepare_sessions(sources: list[Session], overrides: Overrides) -> list[Session]:
    """Expand standalone scientific entries, then apply guarded corrections."""
    sessions = [
        session
        for session in deepcopy(sources)
        if not PROGRAM_END.fullmatch(collapse(session.title))
    ]
    for session in sessions:
        if session.category == "Keynote" and not session.items:
            if not session.label or not re.fullmatch(r"KEYNOTE\s+\d+", session.label):
                raise ValueError(f"keynote needs a numbered source label: {session.title}")
            session.items = [Item(
                label=re.sub(r"\s+", "", session.label),
                title=session_title(session), starts=session.starts, ends=session.ends,
                authors=[a for a in session.authors if not INTRODUCTION_PREFIX.match(a.name)],
                affiliations=session.affiliations,
            )]
        elif (
            session.category == "Late Breaking Symposium"
            and not session.items
            and session.authors
        ):
            if not session.label or not re.fullmatch(
                r"LATE BREAKING SYMPOSIUM\s+\d+", session.label
            ):
                raise ValueError(
                    f"late-breaking symposium needs a numbered source label: {session.title}"
                )
            session.items = [Item(
                label=re.sub(r"\s+", "", session.label),
                title=session_title(session), starts=session.starts, ends=session.ends,
                authors=session.authors,
                affiliations=session.affiliations,
            )]

    apply_item_time_overrides(sessions, overrides)

    corrected: set[tuple[str, str, str, str]] = set()
    for entry in overrides.sessions:
        required = {"match", "presentation", "expect", "presenters", "reason"}
        if set(entry) not in (required, required | {"allow_missing_presenter"}):
            raise ValueError(
                "session override needs match, presentation, expect, presenters, reason, "
                "and optional allow_missing_presenter"
            )
        match, expected = entry["match"], entry["expect"]
        if not isinstance(match, dict) or set(match) != {"title", "date", "starts"}:
            raise ValueError("session override match needs exact source title, date, starts")
        if not isinstance(expected, dict) or set(expected) != {"authors", "presenters"}:
            raise ValueError("session override expect needs authors and presenters")
        strings = [*match.values(), entry["presentation"], entry["reason"]]
        lists = [expected["authors"], expected["presenters"], entry["presenters"]]
        if any(not isinstance(v, list) for v in lists):
            raise ValueError("session override authors and presenters must be lists")
        strings.extend(name for names in lists for name in names)
        if any(not isinstance(v, str) or not v.strip() for v in strings):
            raise ValueError("session override values must be nonempty strings")
        allow_missing = entry.get("allow_missing_presenter", False)
        if not isinstance(allow_missing, bool) or bool(entry["presenters"]) == allow_missing:
            raise ValueError(
                "session override needs either distinct presenters or "
                "allow_missing_presenter"
            )
        if len(set(entry["presenters"])) != len(entry["presenters"]):
            raise ValueError("session override needs distinct presenter names")
        matches = [s for s in sessions if
                   (collapse(s.title), s.date, s.starts) ==
                   (match["title"], match["date"], match["starts"])]
        if len(matches) != 1:
            raise ValueError(f"session override matched {len(matches)} sessions: {match}")
        matched_session = matches[0]
        items = [i for i in matched_session.items if i.label == entry["presentation"]]
        if len(items) != 1:
            raise ValueError(f"session override must match one presentation: {entry['presentation']}")
        item = items[0]
        key = (match["title"], match["date"], match["starts"], item.label)
        if key in corrected:
            raise ValueError(f"duplicate session override: {key}")
        corrected.add(key)
        if expected != {
            "authors": [a.name for a in item.authors],
            "presenters": [a.name for a in presenting_authors(item.authors)],
        }:
            raise ValueError(f"session override expectation changed: {key}")
        for name in entry["presenters"]:
            if sum(a.name == name for a in item.authors) != 1:
                raise ValueError(f"override presenter must match exactly one author: {name}")
        for author in item.authors:
            author.presenting = author.name in entry["presenters"]
        if allow_missing:
            session_id = f"S{sessions.index(matched_session) + 1}"
            overrides.allowed_missing_presenters.add(item_id(session_id, item.label))
    apply_insertions(sessions, overrides)
    return sessions


def apply_item_time_overrides(sessions: list[Session], overrides: Overrides) -> None:
    """Apply guarded corrections for item times printed incorrectly in the PDF."""
    for entry in overrides.item_times:
        if set(entry) != {"presentation", "expect", "starts", "reason"}:
            raise ValueError(
                "item time override needs presentation, expect, starts, reason"
            )
        strings = [entry["presentation"], entry["expect"], entry["starts"], entry["reason"]]
        if any(not isinstance(value, str) or not value.strip() for value in strings):
            raise ValueError("item time override values must be nonempty strings")
        items = [
            item
            for session in sessions
            for item in session.items
            if item.label == entry["presentation"]
        ]
        if len(items) != 1 or items[0].starts != entry["expect"]:
            raise ValueError(
                f"item time override source changed: {entry['presentation']}"
            )
        items[0].starts = entry["starts"]


def apply_insertions(sessions: list[Session], overrides: Overrides) -> None:
    """Turn explicitly reviewed source fragments into talks without presenters."""
    for entry in overrides.insertions:
        if set(entry) != {"match", "expect", "reason", "allow_missing_presenter"}:
            raise ValueError("insertion needs match, expect, reason, allow_missing_presenter")
        match = entry["match"]
        if not isinstance(match, dict) or set(match) != {"title", "date", "starts"}:
            raise ValueError("insertion match needs source title, date, starts")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise ValueError("insertion needs a review reason")
        if entry["allow_missing_presenter"] is not True:
            raise ValueError("insertion must explicitly acknowledge the missing presenter")
        targets = [(index, s) for index, s in enumerate(sessions, start=1)
                   if {"title": collapse(s.title), "date": s.date, "starts": s.starts} == match]
        if len(targets) != 1:
            raise ValueError(f"insertion matched {len(targets)} sessions: {match}")
        index, session = targets[0]
        fragments = [f for f in session.unconsumed if asdict(f) == entry["expect"]]
        if len(fragments) != 1:
            raise ValueError(f"insertion source fragment changed or is ambiguous: {match}")
        fragment = fragments[0]
        if fragment.starts is None or not fragment.text:
            raise ValueError("inserted talk needs a source time and title")
        if any(i.starts == fragment.starts for i in session.items):
            raise ValueError(f"insertion conflicts with an extracted talk at {fragment.starts}")
        preceding = [i for i, item in enumerate(session.items) if item.label == fragment.after]
        if len(preceding) != 1:
            raise ValueError("insertion must follow exactly one extracted talk")
        label = f"Uncoded{fragment.starts.replace(':', '')}"
        session.items.insert(preceding[0] + 1, Item(label, fragment.text, starts=fragment.starts))
        session.unconsumed.remove(fragment)
        overrides.allowed_missing_presenters.add(item_id(f"S{index}", label))
    for session in sessions:
        for fragment in session.unconsumed:
            overrides.unconsumed.append(
                f"unconsumed text on PDF page {fragment.page}, y={fragment.top}, "
                f"time={fragment.starts or '<none>'}, after {fragment.after}: {fragment.text}"
            )


def build_program_sessions(
    source_sessions: list[Session], people: People, overrides: Overrides
) -> list[dict[str, Any]]:
    """Convert the linear program into schema sessions."""
    source_sessions = prepare_sessions(source_sessions, overrides)
    titles = [session_title(session) for session in source_sessions]
    duplicated = {title for title in titles if titles.count(title) > 1}
    seen: dict[str, int] = {}
    sessions: list[dict[str, Any]] = []

    for index, source in enumerate(source_sessions, start=1):
        session_id = f"S{index}"
        title = titles[index - 1]
        seen[title] = seen.get(title, 0) + 1
        category = source.category
        if not category and STANDALONE_EVENT.match(title):
            category = "Social"
        if title in duplicated:
            title = f"{title} {seen[title]}"

        chairs: list[dict[str, str]] = []
        for line in source.chair_lines:
            curated = overrides.chair_people(collapse(line))
            if curated is not None:
                chairs.extend(curated)

        chair_ids = [
            person_id
            for chair in chairs
            if (person_id := people.add(chair["name"], chair.get("org", "")))
            is not None
        ]
        credits = speaker_ids(source.authors, source.affiliations, people, overrides)
        speakers = list(dict.fromkeys(chair_ids + credits))

        description: list[str] = []
        if chairs:
            names = ", ".join(chair["name"] for chair in chairs)
            description.append(f"{'Chairs' if len(chairs) > 1 else 'Chair'}: {names}")
        description.extend(source.description)

        session: dict[str, Any] = {
            "kind": "session",
            "id": session_id,
            "title": title,
            "date": source.date,
            "location": schedule.MAIN_HALL,
            "presentations": [
                build_talk(session_id, source, item, people, overrides)
                for item in source.items
            ],
        }
        if starts := timestamp(source.date, source.starts):
            session["starts_at"] = starts
        if ends := timestamp(source.date, source.ends):
            session["ends_at"] = ends
        if category:
            session["category"] = category
        if speakers:
            session["speaker_ids"] = speakers
        if description:
            session["description_html"] = paragraphs_html(description)
        sessions.append(session)
    return sessions


def presenter_id(
    poster: posters_pdf.Poster, people: People, overrides: Overrides
) -> str | None:
    """Register the poster's named presenter, matched to their author entry.

    The presenter line repeats one of the authors in display casing, so it must
    resolve to that author, with their affiliation, rather than to a bare double.
    """
    speakers = presenting_authors(poster.authors)
    if len(speakers) == 1:
        speaker = speakers[0]
        return people.add(
            speaker.name, author_org(speaker, poster.affiliations, overrides)
        )
    # The presenter is named but matches no author; keep them anyway.
    if overrides.posters.get(poster.label, {}).get("allow_external_presenter") != poster.presenter:
        overrides.unmatched_presenters.add(f"{poster.label}: {poster.presenter or '<empty>'}")
    return people.add(poster.presenter)


def build_poster_sessions(
    posters: list[posters_pdf.Poster], people: People, overrides: Overrides
) -> list[dict[str, Any]]:
    """Group posters by theme, retaining their published display windows."""
    grouped: dict[str, list[posters_pdf.Poster]] = {}
    for poster in posters:
        schedule.session_for_theme(poster.theme)
        if poster.theme not in schedule.POSTER_THEME_IDS:
            raise KeyError(f"no stable session id for theme {poster.theme!r}")
        grouped.setdefault(poster.theme, []).append(poster)

    sessions: list[dict[str, Any]] = []
    for theme, theme_id in schedule.POSTER_THEME_IDS.items():
        members = grouped.get(theme, [])
        if not members:
            continue
        published = schedule.session_for_theme(theme)
        presentations: list[dict[str, Any]] = []
        for poster in members:
            presentation: dict[str, Any] = {
                "kind": "poster",
                "id": poster.label,
                "title": overrides.repair(collapse(poster.title)),
                "location": poster.label + (" [Remote]" if poster.remote else ""),
                "description_html": authors_html(
                    poster.authors,
                    poster.affiliations,
                    overrides,
                    presenting_authors(poster.authors),
                ),
            }
            if person_id := presenter_id(poster, people, overrides):
                presentation["speaker_ids"] = [person_id]
            if overrides.posters.get(poster.label, {}).get("allow_external_presenter"):
                presentation["description_html"] = (
                    f"Presenter: <b>{escape(normalize_name(poster.presenter))}</b><br>"
                    + presentation["description_html"]
                )
            presentations.append(presentation)

        session: dict[str, Any] = {
            "kind": "poster-session",
            "id": theme_id,
            "title": titleize(theme),
            "date": published.date,
            "location": schedule.POSTER_HALL,
            "presentations": presentations,
        }
        if starts := timestamp(published.date, published.starts):
            session["starts_at"] = starts
        if ends := timestamp(published.ends_on or published.date, published.ends):
            session["ends_at"] = ends
        session["description_html"] = paragraphs_html([published.title])
        sessions.append(session)
    return sessions


def sort_key(session: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        session["date"],
        session.get("starts_at", "￿"),
        session["title"],
        session["id"],
    )


def apply_poster_overrides(posters: list[posters_pdf.Poster], overrides: Overrides) -> None:
    """Apply reviewed poster corrections, rejecting changed source expectations."""
    by_id = {poster.label: poster for poster in posters}
    for label, correction in overrides.posters.items():
        poster = by_id.get(label)
        if poster is None or poster.presenter != correction["presenter"]:
            raise ValueError(f"Poster override no longer matches: {label}")
        for before, replacements in correction.get("authors", {}).items():
            matches = [author for author in poster.authors if author.name == before]
            if len(matches) != 1:
                raise ValueError(f"Poster author override no longer matches: {label}: {before}")
            index = poster.authors.index(matches[0])
            poster.authors[index:index + 1] = [Author(**entry) for entry in replacements]
        for key, change in correction.get("affiliations", {}).items():
            if poster.affiliations.get(int(key)) != change["expect"]:
                raise ValueError(f"Poster affiliation override no longer matches: {label}: {key}")
            poster.affiliations.pop(int(key))
            poster.affiliations.update({int(k): v for k, v in change["replace"].items()})
        posters_pdf.mark_presenter(poster)


def build(source_dir: Path = SOURCE_DIR) -> tuple[dict[str, Any], Overrides]:
    """Build the whole program from the two source PDFs."""
    overrides = Overrides.load()
    people = People(overrides)
    program_sessions = program_pdf.parse(
        _only(source_dir, "program_*.pdf"), schedule.YEAR
    )
    posters = posters_pdf.parse(_only(source_dir, "posters_*.pdf"))

    apply_poster_overrides(posters, overrides)

    sessions = build_program_sessions(program_sessions, people, overrides)
    sessions.extend(build_poster_sessions(posters, people, overrides))
    sessions.sort(key=sort_key)

    program = {
        "schema_version": SCHEMA_VERSION,
        "conference": {
            "id": schedule.CONFERENCE_ID,
            "name": schedule.CONFERENCE_NAME,
            "short_name": schedule.CONFERENCE_SHORT_NAME,
            "starts_on": schedule.STARTS_ON,
            "ends_on": schedule.ENDS_ON,
            "timezone": schedule.TIMEZONE,
        },
        "days": sorted({session["date"] for session in sessions}),
        "sessions": sessions,
        "people": people.as_record(),
    }
    return program, overrides


def _only(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"expected exactly one {pattern} in {directory}, found {len(matches)}"
        )
    return matches[0]


def report(program: dict[str, Any], overrides: Overrides) -> list[str]:
    """Describe anything a human should look at before publishing."""
    notes: list[str] = list(overrides.unconsumed)
    unused = [
        ("chair", set(overrides.chairs) - overrides.used_chairs),
        ("name", set(overrides.names) - overrides.used_names),
        ("org", set(overrides.orgs) - overrides.used_orgs),
    ]
    for kind, entries in unused:
        for line in sorted(entries):
            notes.append(f"unused {kind} override (source changed?): {line[:90]}")
    for line in sorted(overrides.uncurated_chairs):
        notes.append(f"uncurated chair line: {line[:90]}")
    for presenter in sorted(overrides.unmatched_presenters):
        notes.append(f"presenter does not match exactly one author: {presenter[:90]}")

    for session in program["sessions"]:
        if not session["presentations"]:
            category = session.get("category", "")
            if category.startswith("Late Breaking"):
                notes.append(f"awaiting presentation details {session['id']}: {session['title']}")
            elif category != "Social" and not STANDALONE_EVENT.match(session["title"]):
                notes.append(f"unexpected empty session {session['id']}: {session['title']}")
        if "starts_at" not in session or "ends_at" not in session:
            missing = [
                field for field in ("starts_at", "ends_at") if field not in session
            ]
            notes.append(
                f"missing session bound in {session['id']}: {', '.join(missing)}"
            )
        for item in session["presentations"]:
            if (item["kind"] == "talk" and "speaker_ids" not in item
                    and item["id"] not in overrides.allowed_missing_presenters):
                notes.append(f"no presenting author resolved for {item['id']}")
        items: list[dict[str, Any]] = [session, *session["presentations"]]
        for item in items:
            if UNMAPPED_GLYPH.search(item["title"]):
                notes.append(f"unmapped glyph in {item['id']}: {item['title'][:90]}")
            description = item.get("description_html", "")
            for literal in overrides.posters.get(item["id"], {}).get("literal_question_marks", []):
                description = description.replace(escape(literal), "")
            if UNMAPPED_GLYPH.search(description):
                notes.append(
                    f"unmapped glyph in {item['id']} description: "
                    f"{collapse(description)[:90]}"
                )
    for person_id, person in program["people"].items():
        if UNMAPPED_GLYPH.search(f"{person['name']} {person.get('org', '')}"):
            notes.append(f"unmapped glyph in person {person_id}: {person['name']}")
        if DIGIT_IN_NAME.search(person["name"]):
            notes.append(f"digit in person name {person_id}: {person['name']}")
    return notes


def blocking_notes(notes: list[str]) -> list[str]:
    """Return review findings that should fail an automated build."""
    return [
        note
        for note in notes
        if not note.startswith(INFORMATIONAL_REVIEW_PREFIXES)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=PROGRAM_CANDIDATE,
        help="candidate program path (default: app/.programs/ctad-2026.json)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="only print the review report, without writing the candidate",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when the report contains an actionable finding",
    )
    arguments = parser.parse_args(argv)

    program, overrides = build()
    notes = report(program, overrides)

    if not arguments.report:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(program, ensure_ascii=False), encoding="utf-8"
        )
        talks = sum(len(s["presentations"]) for s in program["sessions"])
        print(
            f"wrote {arguments.output}: {len(program['days'])} days, "
            f"{len(program['sessions'])} sessions, {talks} presentations, "
            f"{len(program['people'])} people"
        )
    if arguments.report:
        for note in notes:
            print(f"review: {note}", file=sys.stderr)
    else:
        actionable = blocking_notes(notes)
        for note in actionable:
            print(f"review: {note}", file=sys.stderr)
        informational = len(notes) - len(actionable)
        if informational:
            print(
                f"review: {informational} sessions await presentation details; "
                "run with --report for the list",
                file=sys.stderr,
            )
    return 1 if arguments.strict and blocking_notes(notes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
