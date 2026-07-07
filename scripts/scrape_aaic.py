#!/usr/bin/env python3
"""Dump AAIC 2026 EventPilot agenda data to local JSON and CSV files."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


CONFID = "ALZ19292F861B994564D"
BASE = "https://eppro01.ativ.me/web"
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


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


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
        "time_summary",
        "detail_time",
        "location",
        "session_number",
        "speakers_summary",
        "presentation_count",
        "presentation_titles",
    ]
    with (outdir / "sessions.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{field_name: row.get(field_name, "") for field_name in fields},
                    "presentation_count": len(row.get("presentations", [])),
                    "presentation_titles": " | ".join(
                        item.get("title", "") for item in row.get("presentations", [])
                    ),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie", default=os.environ.get("AAIC_COOKIE", ""))
    parser.add_argument("--outdir", type=Path, default=Path("data/aaic_2026"))
    parser.add_argument("--date", action="append", dest="dates")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--no-details", action="store_true")
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
        rows = [{**row, **previous_by_id.get(row["id"], {})} for row in rows]

    write_outputs(rows, args.outdir)

    if not args.no_details:
        for idx, row in enumerate(rows, 1):
            if args.resume and (row.get("location") or row.get("detail_error")):
                continue
            print(f"detail {idx}/{len(rows)}: {row['id']}", flush=True)
            try:
                row.update(fetch_detail(row["id"], args.cookie))
            except Exception as exc:  # Keep the dump useful even if one page changes.
                row["detail_error"] = str(exc)
            write_outputs(rows, args.outdir)
            time.sleep(args.sleep)

    write_outputs(rows, args.outdir)
    print(f"Wrote {len(rows)} sessions to {args.outdir}", flush=True)


if __name__ == "__main__":
    main()
