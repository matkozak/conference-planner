#!/usr/bin/env python3
"""Dump AAIC 2026 EventPilot agenda data to local JSON and CSV files."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.aaic_2026.paths import DATA_DIR


CONFID = "ALZ19292F861B994564D"
BASE = "https://eppro01.ativ.me/web"
EVENT_TIMEZONE = ZoneInfo("Europe/London")
DEFAULT_DATES = [
    "2026-07-10",
    "2026-07-11",
    "2026-07-12",
    "2026-07-13",
    "2026-07-14",
    "2026-07-15",
    "2026-07-16",
]
ORDER = [
    "start",
    "c.position",
    "case when sessnum='' then '' else 'ZZZZZZZZZ' end, sessnum",
    "UPPER(title)",
    "case when parent='' then '' else 'ZZZZZZZZZ' end, parent",
]


class RequestPacer:
    def __init__(self, interval_s: float) -> None:
        self.interval_s = interval_s
        self.lock = threading.Lock()
        self.next_start = 0.0

    def wait(self) -> None:
        if self.interval_s <= 0:
            return
        with self.lock:
            now = time.monotonic()
            wait_s = self.next_start - now
            if wait_s > 0:
                time.sleep(wait_s)
                now = time.monotonic()
            self.next_start = now + self.interval_s


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    def text(self) -> str:
        parts = list(self.text_parts)
        for child in self.children:
            parts.append(child.text())
        return clean_text(" ".join(parts))

    def classes(self) -> set[str]:
        return set(self.attrs.get("class", "").split())

    def has_class(self, class_name: str) -> bool:
        return class_name in self.classes()

    def find_all(self, class_name: str | None = None, tag: str | None = None) -> list["Node"]:
        out: list[Node] = []
        if (class_name is None or self.has_class(class_name)) and (tag is None or self.tag == tag):
            out.append(self)
        for child in self.children:
            out.extend(child.find_all(class_name, tag))
        return out

    def first(self, class_name: str | None = None, tag: str | None = None) -> "Node | None":
        matches = self.find_all(class_name, tag)
        return matches[0] if matches else None


class DOMParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {key: value or "" for key, value in attrs})
        self.stack[-1].children.append(node)
        if tag not in {"br", "hr", "img", "input", "meta", "link"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for idx in range(len(self.stack) - 1, 0, -1):
            if self.stack[idx].tag == tag:
                del self.stack[idx:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.stack[-1].text_parts.append(data)


class DescriptionTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)

    def text(self) -> str:
        lines = [clean_text(line) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def clean_description(value: str) -> str:
    parser = DescriptionTextParser()
    parser.feed(value)
    return parser.text()


def decode_response_xml(payload: bytes) -> tuple[list[Any], str]:
    text = payload.decode("utf-8", errors="replace")
    item_text = ""
    item_msg = ""
    for _ in range(3):
        match = re.search(
            r'<Item\s+success="(?P<success>true|false)"\s+msg=(?P<quote>["\'])(?P<msg>.*?)'
            r'(?P=quote)\s*>(?P<data>.*?)</Item>',
            text,
            re.DOTALL,
        )
        if not match:
            # Last resort for the app's malformed outer wrapper: parse the last
            # XML-ish response, just like EPUtility.ReadResponseXML does.
            marker = '<?xml version="1.0" encoding="utf-8"?>'
            if marker in text and text.split(marker)[-1] != text:
                text = marker + text.split(marker)[-1]
                continue
            raise RuntimeError("Could not parse EventPilot response")
        item_msg = html.unescape(match.group("msg"))
        item_text = match.group("data") or ""
        if match.group("success") != "true":
            raise RuntimeError(f"API failure: {item_msg}")
        decoded = html.unescape(item_text).strip()
        if decoded.startswith("<?xml"):
            text = decoded
            continue
        break
    count = 0
    date = ""
    if item_msg:
        try:
            msg = json.loads(item_msg.replace("&quot;", '"'))
            count = int(msg[0])
            date = str(msg[1]) if len(msg) > 1 else ""
        except (ValueError, TypeError, json.JSONDecodeError):
            pass
    html_text = html.unescape(item_text)
    return [count, date], html_text


def decode_item_json(payload: bytes) -> dict[str, Any]:
    _, text = decode_response_xml(payload)
    return json.loads(text)


def parse_html_fragment(fragment: str) -> Node:
    parser = DOMParser()
    parser.feed(fragment)
    return parser.root


def class_text(node: Node, class_name: str) -> str:
    found = node.first(class_name)
    return found.text() if found else ""


def request(
    url: str,
    cookie: str,
    data: dict[str, Any] | None = None,
    timeout: int = 60,
) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cookie": cookie,
    }
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data, doseq=True).encode()
        headers.update(
            {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": "https://eppro01.ativ.me",
                "Referer": f"{BASE}/plantab.php?id={CONFID}&plannersession=true&tab=urn%3Aeventpilot%3Aplanner%3Aagenda%3A%3A",
            }
        )
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def list_payload(date: str, offset: int, limit: int) -> dict[str, Any]:
    return {
        "interface": "webfilter",
        "action": "getlist",
        "confid": CONFID,
        "table": "agenda",
        "filters[0][field]": "parent",
        "filters[0][val]": "",
        "filters[1][field]": "date",
        "filters[1][val]": date,
        "order[]": ORDER,
        "offset": str(offset),
        "limit": str(limit),
        "adapter": "PlannerAgendaDayListView",
        "urn": "urn:eventpilot:planner:agenda::",
        "selectonly": "",
    }


def table_payload(table: str, tid: str) -> dict[str, str]:
    return {
        "interface": "eptable",
        "action": "gettabledata",
        "confid": CONFID,
        "table": table,
        "tid": tid,
    }


def split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def iso_range(date: str, start: str, stop: str) -> tuple[str, str]:
    if not date or not start or not stop:
        return "", ""
    start_dt = datetime.fromisoformat(f"{date}T{start}").replace(tzinfo=EVENT_TIMEZONE)
    stop_dt = datetime.fromisoformat(f"{date}T{stop}").replace(tzinfo=EVENT_TIMEZONE)
    if stop_dt < start_dt:
        stop_dt += timedelta(days=1)
    return start_dt.isoformat(), stop_dt.isoformat()


def normalize_agenda_item(raw: dict[str, Any]) -> dict[str, Any]:
    starts_at, ends_at = iso_range(
        str(raw.get("date") or ""),
        str(raw.get("start") or ""),
        str(raw.get("stop") or ""),
    )
    description_html = str(raw.get("description") or "")
    item = {
        "id": raw.get("sessionid") or "",
        "parent_id": raw.get("parent") or "",
        "date": raw.get("date") or "",
        "starts_at": starts_at,
        "ends_at": ends_at,
        "title": raw.get("title") or "",
        "description_html": description_html,
        "description_text": clean_description(description_html),
        "location": raw.get("location") or "",
        "category": raw.get("category") or raw.get("categoryid") or "",
        "category_id": raw.get("categoryid") or "",
        "session_number": raw.get("sessnum") or "",
        "speaker_ids": split_ids(raw.get("speaker")),
        "person_ids": split_ids(raw.get("personid")),
        "subsession_ids": split_ids(raw.get("subsessions")),
        "media": raw.get("media"),
        "metadata": {
            "primary_topic": raw.get("metadata1"),
            "secondary_topics": split_ids(raw.get("metadata2")),
            "metadata3": raw.get("metadata3"),
            "metadata4": raw.get("metadata4"),
        },
        "related_ids": split_ids(raw.get("sessionid2")),
        "related_scores": split_ids(raw.get("recposition")),
    }
    return item


def parse_list_cells(fragment: str) -> list[dict[str, Any]]:
    root = parse_html_fragment(fragment)
    rows = []
    for cell in root.find_all("agenda_cell"):
        session_id = cell.attrs.get("data-id", "")
        if not session_id:
            continue
        rows.append(
            {
                "id": session_id,
                "date": cell.attrs.get("data-date", ""),
                "category": class_text(cell, "category_label"),
                "title": class_text(cell, "session_title"),
                "time_summary": class_text(cell, "date_time"),
                "speakers_summary": class_text(cell, "session_speaker"),
            }
        )
    return rows


def parse_detail(html_text: str) -> dict[str, Any]:
    root = parse_html_fragment(html_text)
    title = class_text(root, "session_detail_title")
    location_node = root.first("session_detail_location")
    location = location_node.text() if location_node else ""
    session_number = class_text(root, "sessionnumber")

    detail_time = ""
    time_node = root.first("session_detail_time")
    if time_node:
        time_buttons = [n.text() for n in time_node.find_all("session_detail_day") if n.text()]
        detail_time = " | ".join(time_buttons[:2])

    speakers = []
    for speaker in root.find_all("speaker_cell"):
        name = class_text(speaker, "list_cell_title")
        affiliation_nodes = speaker.find_all("epcelldraw_sub")
        affiliation = affiliation_nodes[-1].text() if affiliation_nodes else ""
        if name:
            speakers.append({"name": name, "affiliation": affiliation})

    presentations = []
    for session_cell in root.find_all("session_cell"):
        node_id = session_cell.attrs.get("id", "")
        match = re.search(r"agendacell_([^_]+)_", node_id)
        presentation_id = match.group(1) if match else ""
        if not presentation_id.startswith("P"):
            continue
        title_text = class_text(session_cell, "list_cell_title")
        sub = class_text(session_cell, "epcelldraw_sub")
        if title_text:
            presentations.append(
                {
                    "id": presentation_id,
                    "title": title_text,
                    "time_and_speaker": sub,
                }
            )

    return {
        "detail_title": title,
        "detail_time": detail_time,
        "location": location,
        "session_number": session_number,
        "speakers": speakers,
        "presentations": presentations,
    }


def fetch_list(date: str, cookie: str, limit: int, sleep_s: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        payload = request(f"{BASE}/api.php", cookie, list_payload(date, offset, limit))
        meta, fragment = decode_response_xml(payload)
        page_rows = parse_list_cells(fragment)
        rows.extend(page_rows)
        print(f"{date} offset {offset}: {len(page_rows)} rows", flush=True)
        if meta[0] == 0 or len(page_rows) == 0:
            break
        offset += limit
        time.sleep(sleep_s)
    return rows


def fetch_detail(session_id: str, cookie: str) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "nav": "false",
            "page": "Session",
            "project": CONFID,
            "id": session_id,
            "plannersession": "true",
        }
    )
    payload = request(f"{BASE}/page.php?{query}", cookie)
    return parse_detail(payload.decode("utf-8", errors="replace"))


def fetch_agenda_item(item_id: str, cookie: str) -> dict[str, Any]:
    payload = request(f"{BASE}/api.php", cookie, table_payload("agenda", item_id))
    return normalize_agenda_item(decode_item_json(payload))


def normalize_person(raw: dict[str, Any], person_id: str) -> dict[str, Any]:
    first_name = str(raw.get("firstname") or raw.get("first") or raw.get("fname") or "")
    last_name = str(raw.get("lastname") or raw.get("last") or raw.get("lname") or "")
    full_name = clean_text(
        str(
            raw.get("name")
            or raw.get("fullname")
            or raw.get("displayname")
            or f"{first_name} {last_name}"
        )
    )
    organization = str(
        raw.get("organization")
        or raw.get("org")
        or raw.get("company")
        or raw.get("affiliation")
        or ""
    )
    return {
        "id": str(
            raw.get("speakerid")
            or raw.get("personid")
            or raw.get("id")
            or raw.get("tid")
            or person_id
        ),
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "degree": str(raw.get("degree") or raw.get("degrees") or ""),
        "organization": organization,
        "country": str(raw.get("country") or ""),
        "city": str(raw.get("city") or ""),
        "state": str(raw.get("state") or raw.get("province") or ""),
        "profile_html": str(raw.get("profile") or raw.get("bio") or raw.get("description") or ""),
        "raw": raw,
    }


def fetch_person(person_id: str, cookie: str) -> dict[str, Any]:
    payload = request(f"{BASE}/api.php", cookie, table_payload("speakers", person_id))
    return normalize_person(decode_item_json(payload), person_id)


def fetch_agenda_item_paced(item_id: str, cookie: str, pacer: RequestPacer) -> dict[str, Any]:
    pacer.wait()
    return fetch_agenda_item(item_id, cookie)


def fetch_person_paced(person_id: str, cookie: str, pacer: RequestPacer) -> dict[str, Any]:
    pacer.wait()
    return fetch_person(person_id, cookie)


def fetch_detail_paced(
    idx: int,
    total: int,
    session_id: str,
    cookie: str,
    pacer: RequestPacer,
) -> tuple[int, int, str, dict[str, Any], float]:
    started = time.monotonic()
    detail = fetch_agenda_item_paced(session_id, cookie, pacer)
    return idx, total, session_id, detail, time.monotonic() - started


def fetch_person_paced_job(
    idx: int,
    total: int,
    person_id: str,
    cookie: str,
    pacer: RequestPacer,
) -> tuple[int, int, str, dict[str, Any], float]:
    started = time.monotonic()
    person = fetch_person_paced(person_id, cookie, pacer)
    return idx, total, person_id, person, time.monotonic() - started


def discover_dates() -> list[str]:
    local_tab = Path("plantab_agenda.html")
    if local_tab.exists():
        dates = sorted(set(re.findall(r'data-date="(\d{4}-\d{2}-\d{2})"', local_tab.read_text())))
        if dates:
            return dates
    return DEFAULT_DATES


def write_outputs(rows: list[dict[str, Any]], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "sessions.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False))

    fields = [
        "id",
        "date",
        "category",
        "title",
        "starts_at",
        "ends_at",
        "location",
        "session_number",
        "speaker_ids",
        "presentation_count",
    ]
    with (outdir / "sessions.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{
                        field_name: row.get(field_name, "")
                        for field_name in fields
                        if field_name != "speaker_ids"
                    },
                    "speaker_ids": ",".join(row.get("speaker_ids", [])),
                    "presentation_count": len(row.get("presentations", [])),
                }
            )


def collect_person_ids(rows: list[dict[str, Any]]) -> list[str]:
    ids: set[str] = set()
    for row in rows:
        ids.update(row.get("speaker_ids", []))
        ids.update(row.get("person_ids", []))
        for presentation in row.get("presentations", []):
            ids.update(presentation.get("speaker_ids", []))
            ids.update(presentation.get("person_ids", []))
    return sorted(
        ids,
        key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value),
    )


def write_people(people: dict[str, dict[str, Any]], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    ordered = {person_id: people[person_id] for person_id in sorted(people, key=str)}
    (outdir / "people.json").write_text(json.dumps(ordered, indent=2, ensure_ascii=False))


def fetch_people(
    rows: list[dict[str, Any]],
    cookie: str,
    outdir: Path,
    resume: bool,
    workers: int,
    interval_s: float,
    save_every: int,
    log_every: int,
) -> dict[str, dict[str, Any]]:
    person_ids = collect_person_ids(rows)
    people: dict[str, dict[str, Any]] = {}
    people_path = outdir / "people.json"
    if resume and people_path.exists():
        previous = json.loads(people_path.read_text(encoding="utf-8"))
        people = {person_id: previous[person_id] for person_id in person_ids if person_id in previous}

    jobs = [
        person_id
        for person_id in person_ids
        if not (
            resume
            and person_id in people
            and people[person_id].get("full_name")
            and not people[person_id].get("detail_error")
        )
    ]
    if not jobs:
        print(f"people: 0 rows to fetch ({len(people)} already present)", flush=True)
        return people

    workers = max(1, workers)
    pacer = RequestPacer(interval_s)
    completed = 0
    changed = 0
    print(
        f"people: fetching {len(jobs)} rows with {workers} workers "
        f"and {interval_s:.2f}s request-start interval",
        flush=True,
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                fetch_person_paced_job,
                idx,
                len(jobs),
                person_id,
                cookie,
                pacer,
            ): person_id
            for idx, person_id in enumerate(jobs, 1)
        }
        for future in concurrent.futures.as_completed(futures):
            person_id = futures[future]
            completed += 1
            changed += 1
            try:
                idx, total, _, person, elapsed_s = future.result()
            except Exception as exc:
                marker = " possible-rate-limit" if looks_like_rate_limit(exc) else ""
                people[person_id] = {"id": person_id, "detail_error": str(exc)}
                print(
                    f"person {completed}/{len(jobs)} error {person_id}: "
                    f"{type(exc).__name__}: {exc}{marker}",
                    flush=True,
                )
            else:
                people[person_id] = person
                if completed == 1 or completed == len(jobs) or (
                    log_every > 0 and completed % log_every == 0
                ):
                    print(
                        f"person {completed}/{len(jobs)} ok row {idx}/{total}: "
                        f"{person_id} {elapsed_s:.2f}s {person.get('full_name', '')!r}",
                        flush=True,
                    )

            if save_every > 0 and changed >= save_every:
                write_people(people, outdir)
                changed = 0

    if changed:
        write_people(people, outdir)
    return people


def looks_like_rate_limit(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {403, 429, 503}
    return any(marker in str(exc).lower() for marker in ("too many", "rate", "throttle"))


def agenda_item_complete(row: dict[str, Any]) -> bool:
    """Whether a row came from the agenda table rather than a list/checkpoint stub."""
    return bool(row.get("id") and "parent_id" in row and not row.get("detail_error"))


def presentation_work(
    rows: list[dict[str, Any]], resume: bool
) -> tuple[dict[str, dict[str, Any]], list[tuple[int, str]]]:
    """Return preserved presentation details and the detail jobs still needed."""
    preserved: dict[str, dict[str, Any]] = {}
    if resume:
        for row in rows:
            for presentation in row.get("presentations", []):
                presentation_id = str(presentation.get("id") or "")
                if presentation_id and agenda_item_complete(presentation):
                    preserved[presentation_id] = presentation

    presentation_ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for presentation_id in map(str, row.get("subsession_ids", [])):
            if presentation_id not in seen:
                seen.add(presentation_id)
                presentation_ids.append(presentation_id)

    jobs = [
        (idx, presentation_id)
        for idx, presentation_id in enumerate(
            (item_id for item_id in presentation_ids if item_id not in preserved), 1
        )
    ]
    return preserved, jobs


def attach_presentations(
    rows: list[dict[str, Any]], presentations_by_id: dict[str, dict[str, Any]]
) -> None:
    """Attach every available presentation detail to its parent session."""
    for row in rows:
        row["presentations"] = [
            presentations_by_id[presentation_id]
            for presentation_id in map(str, row.get("subsession_ids", []))
            if presentation_id in presentations_by_id
        ]


def fetch_details(
    rows: list[dict[str, Any]],
    cookie: str,
    outdir: Path,
    resume: bool,
    workers: int,
    interval_s: float,
    save_every: int,
    log_every: int,
) -> None:
    presentations_by_id, _ = presentation_work(rows, resume)
    detail_rows = [
        (idx, row)
        for idx, row in enumerate(rows, 1)
        if not (resume and agenda_item_complete(row))
    ]
    workers = max(1, workers)
    pacer = RequestPacer(interval_s)
    if not detail_rows:
        print("detail: 0 rows to fetch", flush=True)
    else:
        completed = 0
        changed = 0
        total = len(rows)
        print(
            f"detail: fetching {len(detail_rows)} rows with {workers} workers "
            f"and {interval_s:.2f}s request-start interval",
            flush=True,
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(fetch_detail_paced, idx, total, row["id"], cookie, pacer): row
                for idx, row in detail_rows
            }
            for future in concurrent.futures.as_completed(futures):
                row = futures[future]
                completed += 1
                changed += 1
                try:
                    idx, total, session_id, detail, elapsed_s = future.result()
                except Exception as exc:  # Keep the dump useful even if one page changes.
                    row["detail_error"] = str(exc)
                    marker = " possible-rate-limit" if looks_like_rate_limit(exc) else ""
                    print(
                        f"detail {completed}/{len(detail_rows)} error {row['id']}: "
                        f"{type(exc).__name__}: {exc}{marker}",
                        flush=True,
                    )
                else:
                    row.clear()
                    row.update(detail)
                    print(
                        f"detail {completed}/{len(detail_rows)} ok row {idx}/{total}: "
                        f"{session_id} {elapsed_s:.2f}s "
                        f"subsessions={len(detail.get('subsession_ids', []))} "
                        f"location={detail.get('location', '')!r}",
                        flush=True,
                    )

                if save_every > 0 and changed >= save_every:
                    attach_presentations(rows, presentations_by_id)
                    write_outputs(rows, outdir)
                    changed = 0

        if changed:
            attach_presentations(rows, presentations_by_id)
            write_outputs(rows, outdir)

    # Parent records may have been replaced above, so derive the final job list
    # only after their current subsession ids are known.
    _, presentation_jobs = presentation_work(rows, resume)

    if not presentation_jobs:
        attach_presentations(rows, presentations_by_id)
        write_outputs(rows, outdir)
        print(
            f"presentation details: 0 rows to fetch ({len(presentations_by_id)} already present)",
            flush=True,
        )
        return

    print(
        f"presentation details: fetching {len(presentation_jobs)} rows with {workers} workers "
        f"and {interval_s:.2f}s request-start interval",
        flush=True,
    )
    changed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                fetch_detail_paced,
                idx,
                len(presentation_jobs),
                presentation_id,
                cookie,
                pacer,
            ): presentation_id
            for idx, presentation_id in presentation_jobs
        }
        for future in concurrent.futures.as_completed(futures):
            presentation_id = futures[future]
            changed += 1
            try:
                idx, total, _, detail, elapsed_s = future.result()
            except Exception as exc:
                marker = " possible-rate-limit" if looks_like_rate_limit(exc) else ""
                presentations_by_id[presentation_id] = {
                    "id": presentation_id,
                    "detail_error": str(exc),
                }
                print(
                    f"presentation {changed}/{len(presentation_jobs)} error {presentation_id}: "
                    f"{type(exc).__name__}: {exc}{marker}",
                    flush=True,
                )
            else:
                presentations_by_id[presentation_id] = detail
                if changed == 1 or changed == len(presentation_jobs) or (
                    log_every > 0 and changed % log_every == 0
                ):
                    print(
                        f"presentation {changed}/{len(presentation_jobs)} ok row {idx}/{total}: "
                        f"{presentation_id} {elapsed_s:.2f}s "
                        f"location={detail.get('location', '')!r}",
                        flush=True,
                    )

            if save_every > 0 and changed % save_every == 0:
                attach_presentations(rows, presentations_by_id)
                write_outputs(rows, outdir)

    attach_presentations(rows, presentations_by_id)
    write_outputs(rows, outdir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie", default=os.environ.get("AAIC_COOKIE", ""))
    parser.add_argument(
        "--outdir",
        type=Path,
        required=True,
        help=f"output directory (canonical data is {DATA_DIR})",
    )
    parser.add_argument("--date", action="append", dest="dates")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--detail-workers", type=int, default=3)
    parser.add_argument("--detail-interval", type=float, default=0.05)
    parser.add_argument("--save-every", type=int, default=100)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument("--no-details", action="store_true")
    parser.add_argument("--people", action="store_true")
    parser.add_argument("--people-workers", type=int, default=3)
    parser.add_argument("--people-interval", type=float, default=0.05)
    parser.add_argument("--max-sessions", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not args.cookie:
        raise SystemExit("Pass --cookie or set AAIC_COOKIE.")

    dates = args.dates or discover_dates()
    rows: list[dict[str, Any]] = []
    for date in dates:
        rows.extend(fetch_list(date, args.cookie, args.limit, args.sleep))
        if args.max_sessions and len(rows) >= args.max_sessions:
            rows = rows[: args.max_sessions]
            break

    if args.resume and (args.outdir / "sessions.json").exists():
        previous = json.loads((args.outdir / "sessions.json").read_text())
        previous_by_id = {row.get("id"): row for row in previous}
        rows = [previous_by_id.get(row["id"], row) for row in rows]

    write_outputs(rows, args.outdir)

    if not args.no_details:
        fetch_details(
            rows,
            args.cookie,
            args.outdir,
            args.resume,
            args.detail_workers,
            args.detail_interval,
            args.save_every,
            args.log_every,
        )

    write_outputs(rows, args.outdir)
    if args.people:
        fetch_people(
            rows,
            args.cookie,
            args.outdir,
            args.resume,
            args.people_workers,
            args.people_interval,
            args.save_every,
            args.log_every,
        )
    print(f"Wrote {len(rows)} sessions to {args.outdir}", flush=True)


if __name__ == "__main__":
    main()
