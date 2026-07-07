# AAIC 2026 Program Dump

This workspace contains a small scraper for the AAIC 2026 EventPilot web planner.
It dumps the conference program into local JSON and CSV for planning outside the
official app.

## Current Result

The latest completed dump is in `data/aaic_2026/`:

- `data/aaic_2026/sessions.json`
- `data/aaic_2026/sessions.csv`

Verification from the completed run:

- 360 parent sessions
- 360 sessions with parsed locations
- 6,850 nested presentations
- 0 detail fetch errors
- CSV has 361 lines including the header

## Main Script

Use `scripts/scrape_aaic.py`. It uses only Python standard library modules.

Basic rerun:

```bash
AAIC_COOKIE='miplanner0=...; xphrj=...; xphrj_web=...; web_cc5172e7=...' \
  python3 scripts/scrape_aaic.py --outdir data/aaic_2026 --resume
```

Do not commit or hard-code the cookie. Copy it from a logged-in browser request
to `https://eppro01.ativ.me/web/api.php`.

Useful options:

- `--resume`: merge existing `data/aaic_2026/sessions.json` and skip detail pages
  that already have a location or previous detail error.
- `--no-details`: only fetch the parent session list, without detail pages.
- `--date YYYY-MM-DD`: restrict to one date. Can be repeated.
- `--max-sessions N`: limit a validation run.
- `--sleep 0.15`: delay between requests, in seconds.

Example smoke test:

```bash
AAIC_COOKIE='...' python3 scripts/scrape_aaic.py \
  --date 2026-07-12 \
  --max-sessions 2 \
  --outdir aaic_sample
```

## Data Flow

The planner shell is:

```text
https://eppro01.ativ.me/src/EventPilot/php/express/web/planner.php?id=ALZ19292F861B994564D
```

The Program tab iframe is:

```text
https://eppro01.ativ.me/web/plantab.php?id=ALZ19292F861B994564D&plannersession=true&tab=urn%3Aeventpilot%3Aplanner%3Aagenda%3A%3A
```

The session list endpoint is:

```text
POST https://eppro01.ativ.me/web/api.php
```

with form data equivalent to:

```text
interface=webfilter
action=getlist
confid=ALZ19292F861B994564D
table=agenda
filters[0][field]=parent
filters[0][val]=
filters[1][field]=date
filters[1][val]=YYYY-MM-DD
order[]=start
order[]=c.position
order[]=case when sessnum='' then '' else 'ZZZZZZZZZ' end, sessnum
order[]=UPPER(title)
order[]=case when parent='' then '' else 'ZZZZZZZZZ' end, parent
offset=0
limit=50
adapter=PlannerAgendaDayListView
urn=urn:eventpilot:planner:agenda::
selectonly=
```

The response is awkward: an EventPilot XML wrapper often contains another
escaped XML response, and the inner response contains escaped HTML list cells.
`scripts/scrape_aaic.py` mirrors the app's tolerant parsing approach and then parses the
HTML cells.

For each parent session, the detail page is:

```text
GET https://eppro01.ativ.me/web/page.php?nav=false&page=Session&project=ALZ19292F861B994564D&id=<SESSION_ID>&plannersession=true
```

The detail page provides:

- location via `session_detail_location`
- full date/time via `session_detail_time`
- session number via `sessionnumber`
- speakers via `speaker_cell`
- nested presentations via `session_cell` entries whose ids start with `P`

## Parsed Output Shape

Each JSON session contains fields like:

```json
{
  "id": "S510",
  "date": "2026-07-12",
  "category": "Featured Research Sessions",
  "title": "Featured Research Sessions - Metabolic adaptations and mitochondrial dysfunction in ADRD",
  "time_summary": "9:00AM-10:30AM Jul 12 (BST)",
  "speakers_summary": "Frederic Calon, Silvia Fossati",
  "detail_time": "Sun, Jul 12 | 9:00am - 10:30am (BST)",
  "location": "Victoria 5/6",
  "session_number": "1-19-FRS-A",
  "speakers": [
    {"name": "Frederic Calon", "affiliation": "Universite Laval"}
  ],
  "presentations": [
    {
      "id": "P2740",
      "title": "Metabolic biomarkers across the AD continuum: insights into how they maycontribute to neuropathology.",
      "time_and_speaker": "9:02am-9:12am Jul 12 (BST) Frederic Calon"
    }
  ]
}
```

The CSV flattens the common planning fields and joins presentation titles with
` | `.

See `STATUS.md` for current caveats and likely next modeling steps.

## Known Local Scratch Files

There are several probe files in the workspace from endpoint discovery:

- `planner.html`, `plantab_agenda.html`, `detail_S510.html`
- `EPUtility.js`, `EPFormat*.js`, `PlannerFilterFunctions.js`
- `agenda_*.txt`, `agenda_*.xml`, `autocomplete_*.txt`, `cookies*.txt`
- `aaic_sample/`

They are not required for normal use. The important files are:

- `scripts/scrape_aaic.py`
- `README.md`
- `STATUS.md`
- `data/aaic_2026/sessions.json`
- `data/aaic_2026/sessions.csv`

## Notes For Next Agent

- Network access may require escalation in the managed sandbox.
- The cookie expires; if requests start returning access errors, copy a fresh
  `Cookie:` header from the browser's Network tab.
- The app returns malformed or nested XML-ish responses. Avoid replacing the
  tolerant decoder with strict XML parsing unless the endpoint changes.
- The script intentionally fetches detail pages serially. It is slower but
  gentler on the logged-in session and server.
