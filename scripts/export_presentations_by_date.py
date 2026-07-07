#!/usr/bin/env python3
"""Export one presentation-level CSV per conference date."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


FIELDS = ["Session time", "Location", "Session name", "Time", "Title", "Presenter"]
TIME_RE = re.compile(r"(?P<start>\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(?P<end>\d{1,2}:\d{2}\s*[ap]m)", re.I)
PRESENTATION_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(?P<end>\d{1,2}:\d{2}\s*[ap]m)"
    r"\s+[A-Z][a-z]{2}\s+\d{1,2}\s+\([A-Z]+\)(?:\s+(?P<presenter>.*))?$",
    re.I,
)


def parse_ampm(value: str) -> int:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([ap]m)", value.strip(), re.I)
    if not match:
        raise ValueError(f"Invalid time: {value!r}")
    hour = int(match.group(1))
    minute = int(match.group(2))
    meridiem = match.group(3).lower()
    if hour == 12:
        hour = 0
    if meridiem == "pm":
        hour += 12
    return hour * 60 + minute


def format_minutes(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def format_range(start: str, end: str) -> tuple[str, int]:
    start_minutes = parse_ampm(start)
    end_minutes = parse_ampm(end)
    return f"{format_minutes(start_minutes)} - {format_minutes(end_minutes)}", start_minutes


def parse_session_time(session: dict[str, Any]) -> tuple[str, int]:
    source = str(session.get("detail_time") or session.get("time_summary") or "")
    match = TIME_RE.search(source)
    if not match:
        return "", 24 * 60
    return format_range(match.group("start"), match.group("end"))


def parse_presentation_time(value: str) -> tuple[str, str, int]:
    match = PRESENTATION_RE.match(value.strip())
    if not match:
        return "", "", 24 * 60
    time_text, start_minutes = format_range(match.group("start"), match.group("end"))
    return time_text, match.group("presenter") or "", start_minutes


def rows_by_date(sessions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        if str(session.get("category") or "").casefold() == "poster":
            continue

        session_date = str(session.get("date") or "unknown-date")
        session_time, session_start = parse_session_time(session)
        location = str(session.get("location") or "")
        session_name = str(session.get("title") or session.get("detail_title") or "")
        presentations = session.get("presentations", [])

        if not presentations:
            rows[session_date].append(
                {
                    "Session time": session_time,
                    "Location": location,
                    "Session name": session_name,
                    "Time": "",
                    "Title": "",
                    "Presenter": "",
                    "_sort": (session_start, location.casefold(), 24 * 60, ""),
                }
            )
            continue

        for presentation in presentations:
            presentation_time, presenter, presentation_start = parse_presentation_time(
                str(presentation.get("time_and_speaker") or "")
            )
            rows[session_date].append(
                {
                    "Session time": session_time,
                    "Location": location,
                    "Session name": session_name,
                    "Time": presentation_time,
                    "Title": str(presentation.get("title") or ""),
                    "Presenter": presenter,
                    "_sort": (
                        session_start,
                        location.casefold(),
                        presentation_start,
                        str(presentation.get("title") or "").casefold(),
                    ),
                }
            )

    for date_rows in rows.values():
        date_rows.sort(key=lambda row: row["_sort"])
    return rows


def write_csvs(rows: dict[str, list[dict[str, Any]]], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for session_date, date_rows in sorted(rows.items()):
        with (outdir / f"presentations_{session_date}.csv").open(
            "w", newline="", encoding="utf-8"
        ) as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            for row in date_rows:
                writer.writerow({field: row[field] for field in FIELDS})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("data/aaic_2026/sessions.json"))
    parser.add_argument("--outdir", type=Path, default=Path("data/aaic_2026"))
    args = parser.parse_args()

    sessions = json.loads(args.input.read_text(encoding="utf-8"))
    rows = rows_by_date(sessions)
    write_csvs(rows, args.outdir)
    print(f"Wrote {len(rows)} presentation CSV files to {args.outdir}")


if __name__ == "__main__":
    main()
