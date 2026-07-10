#!/usr/bin/env python3
"""Export the AAIC JSON dump to a small SQLite database."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def scalar(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json_text(value)
    return value


def iter_presentations(
    sessions: list[dict[str, Any]],
) -> Iterable[tuple[dict[str, Any], dict[str, Any]]]:
    for session in sessions:
        for presentation in session.get("presentations", []):
            yield session, presentation


def people_from_items(sessions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    people: dict[str, dict[str, Any]] = {}
    for item in sessions:
        for person_id in item.get("speaker_ids", []) + item.get("person_ids", []):
            people.setdefault(person_id, {"id": person_id})
        for presentation in item.get("presentations", []):
            person_ids = presentation.get("speaker_ids", []) + presentation.get("person_ids", [])
            for person_id in person_ids:
                people.setdefault(person_id, {"id": person_id})
    return people


def load_people(path: Path | None, sessions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    people = people_from_items(sessions)
    if path and path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            loaded = {str(person.get("id", "")): person for person in loaded if person.get("id")}
        for person_id, person in loaded.items():
            people[str(person_id)] = person
    return people


def reset_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP VIEW IF EXISTS agenda_items;
        DROP TABLE IF EXISTS presentation_people;
        DROP TABLE IF EXISTS session_people;
        DROP TABLE IF EXISTS presentations;
        DROP TABLE IF EXISTS sessions;
        DROP TABLE IF EXISTS people;

        CREATE TABLE sessions (
          id TEXT PRIMARY KEY,
          date TEXT,
          starts_at TEXT,
          ends_at TEXT,
          title TEXT NOT NULL,
          description_html TEXT,
          location TEXT,
          category TEXT,
          category_id TEXT,
          session_number TEXT,
          media TEXT,
          metadata_json TEXT NOT NULL,
          related_ids_json TEXT NOT NULL,
          related_scores_json TEXT NOT NULL,
          subsession_ids_json TEXT NOT NULL
        );

        CREATE TABLE presentations (
          id TEXT PRIMARY KEY,
          parent_session_id TEXT NOT NULL REFERENCES sessions(id),
          date TEXT,
          starts_at TEXT,
          ends_at TEXT,
          title TEXT NOT NULL,
          description_html TEXT,
          location TEXT,
          category TEXT,
          category_id TEXT,
          session_number TEXT,
          media TEXT,
          metadata_json TEXT NOT NULL,
          related_ids_json TEXT NOT NULL,
          related_scores_json TEXT NOT NULL
        );

        CREATE TABLE people (
          id TEXT PRIMARY KEY,
          first_name TEXT,
          last_name TEXT,
          full_name TEXT,
          degree TEXT,
          organization TEXT,
          country TEXT,
          city TEXT,
          state TEXT,
          profile_html TEXT,
          detail_error TEXT
        );

        CREATE TABLE session_people (
          session_id TEXT NOT NULL REFERENCES sessions(id),
          person_id TEXT NOT NULL REFERENCES people(id),
          role TEXT NOT NULL,
          PRIMARY KEY (session_id, person_id, role)
        );

        CREATE TABLE presentation_people (
          presentation_id TEXT NOT NULL REFERENCES presentations(id),
          person_id TEXT NOT NULL REFERENCES people(id),
          role TEXT NOT NULL,
          PRIMARY KEY (presentation_id, person_id, role)
        );

        CREATE INDEX idx_sessions_schedule ON sessions(date, starts_at);
        CREATE INDEX idx_presentations_parent ON presentations(parent_session_id, starts_at);
        CREATE INDEX idx_presentations_schedule ON presentations(date, starts_at);
        CREATE INDEX idx_people_name ON people(last_name, first_name, full_name);

        CREATE VIEW agenda_items AS
          SELECT
            'session' AS item_type,
            id,
            NULL AS parent_session_id,
            date,
            starts_at,
            ends_at,
            title,
            location,
            category,
            session_number,
            description_html
          FROM sessions
          UNION ALL
          SELECT
            'presentation' AS item_type,
            id,
            parent_session_id,
            date,
            starts_at,
            ends_at,
            title,
            location,
            category,
            session_number,
            description_html
          FROM presentations;
        """
    )


def insert_sessions(conn: sqlite3.Connection, sessions: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO sessions (
          id, date, starts_at, ends_at, title, description_html,
          location, category, category_id, session_number, media, metadata_json,
          related_ids_json, related_scores_json, subsession_ids_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                session.get("id"),
                session.get("date"),
                session.get("starts_at"),
                session.get("ends_at"),
                session.get("title") or "",
                session.get("description_html"),
                session.get("location"),
                session.get("category"),
                session.get("category_id"),
                session.get("session_number"),
                scalar(session.get("media")),
                json_text(session.get("metadata") or {}),
                json_text(session.get("related_ids") or []),
                json_text(session.get("related_scores") or []),
                json_text(session.get("subsession_ids") or []),
            )
            for session in sessions
        ],
    )


def insert_presentations(conn: sqlite3.Connection, sessions: list[dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT OR REPLACE INTO presentations (
          id, parent_session_id, date, starts_at, ends_at, title, description_html,
          location, category, category_id, session_number, media, metadata_json,
          related_ids_json, related_scores_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                presentation.get("id"),
                presentation.get("parent_id") or session.get("id"),
                presentation.get("date"),
                presentation.get("starts_at"),
                presentation.get("ends_at"),
                presentation.get("title") or "",
                presentation.get("description_html"),
                presentation.get("location"),
                presentation.get("category"),
                presentation.get("category_id"),
                presentation.get("session_number"),
                scalar(presentation.get("media")),
                json_text(presentation.get("metadata") or {}),
                json_text(presentation.get("related_ids") or []),
                json_text(presentation.get("related_scores") or []),
            )
            for session, presentation in iter_presentations(sessions)
            if presentation.get("id")
        ],
    )


def insert_people(conn: sqlite3.Connection, people: dict[str, dict[str, Any]]) -> None:
    conn.executemany(
        """
        INSERT INTO people (
          id, first_name, last_name, full_name, degree, organization, country,
          city, state, profile_html, detail_error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                person_id,
                person.get("first_name"),
                person.get("last_name"),
                person.get("full_name"),
                person.get("degree"),
                person.get("organization"),
                person.get("country"),
                person.get("city"),
                person.get("state"),
                person.get("profile_html"),
                person.get("detail_error"),
            )
            for person_id, person in people.items()
        ],
    )


def insert_links(conn: sqlite3.Connection, sessions: list[dict[str, Any]]) -> None:
    session_links = set()
    presentation_links = set()
    for session in sessions:
        session_id = session.get("id")
        for person_id in session.get("speaker_ids", []):
            session_links.add((session_id, person_id, "speaker"))
        for person_id in session.get("person_ids", []):
            session_links.add((session_id, person_id, "person"))
        for presentation in session.get("presentations", []):
            presentation_id = presentation.get("id")
            for person_id in presentation.get("speaker_ids", []):
                presentation_links.add((presentation_id, person_id, "speaker"))
            for person_id in presentation.get("person_ids", []):
                presentation_links.add((presentation_id, person_id, "person"))

    conn.executemany(
        "INSERT OR IGNORE INTO session_people (session_id, person_id, role) VALUES (?, ?, ?)",
        sorted(link for link in session_links if link[0] and link[1]),
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO presentation_people (presentation_id, person_id, role)
        VALUES (?, ?, ?)
        """,
        sorted(link for link in presentation_links if link[0] and link[1]),
    )


def export_sqlite(sessions_path: Path, people_path: Path | None, output_path: Path) -> None:
    sessions = json.loads(sessions_path.read_text(encoding="utf-8"))
    people = load_people(people_path, sessions)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(output_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        reset_schema(conn)
        insert_sessions(conn, sessions)
        insert_presentations(conn, sessions)
        insert_people(conn, people)
        insert_links(conn, sessions)
        conn.commit()
        conn.execute("VACUUM")
        conn.execute("PRAGMA optimize")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=Path, default=Path("data/aaic_2026/sessions.json"))
    parser.add_argument("--people", type=Path, default=Path("data/aaic_2026/people.json"))
    parser.add_argument("--output", type=Path, default=Path("data/aaic_2026/aaic_2026.sqlite"))
    args = parser.parse_args()

    people_path = args.people if args.people.exists() else None
    export_sqlite(args.sessions, people_path, args.output)
    print(f"Wrote SQLite database to {args.output}")


if __name__ == "__main__":
    main()
