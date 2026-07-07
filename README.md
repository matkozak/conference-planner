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
- `--sleep 0.15`: delay between session-list page requests, in seconds.
- `--detail-workers 3`: concurrent agenda-detail fetches.
- `--detail-interval 0.05`: minimum delay between detail request starts, in seconds.
- `--save-every 100`: write partial JSON/CSV progress after this many detail results.
- `--log-every 50`: log every Nth successful presentation detail; errors always log.
- `--people`: fetch unique `speaker_ids`/`person_ids` from the EventPilot
  `speakers` table and write `people.json`.
- `--people-workers 3`: concurrent speaker/person fetches.
- `--people-interval 0.05`: minimum delay between speaker/person request starts.

Agenda detail records are fetched concurrently but conservatively. The default
of 3 workers with a 0.05 second request-start interval is intended to get a
basic speed-up from network overlap without hammering a logged-in EventPilot PHP
session. Detail logs include per-record timing and mark likely rate-limit
errors.

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

For each agenda item, the detail endpoint is:

```text
POST https://eppro01.ativ.me/web/api.php
```

with form data:

```text
interface=eptable
action=gettabledata
confid=ALZ19292F861B994564D
table=agenda
tid=<SESSION_OR_PRESENTATION_ID>
```

The agenda table detail response provides:

- description HTML
- date plus start/stop times
- location
- session number
- speaker/person ids
- nested presentation ids via `subsessions`

## Parsed Output Shape

Each JSON session contains fields like:

```json
{
  "id": "S510",
  "date": "2026-07-12",
  "category": "Featured Research Sessions",
  "title": "Featured Research Sessions - Metabolic adaptations and mitochondrial dysfunction in ADRD",
  "starts_at": "2026-07-12T09:00:00+01:00",
  "ends_at": "2026-07-12T10:30:00+01:00",
  "location": "Victoria 5/6",
  "session_number": "1-19-FRS-A",
  "description_html": "",
  "description_text": "",
  "speaker_ids": ["1926", "749"],
  "subsession_ids": ["P16407", "P2740"],
  "presentations": [
    {
      "id": "P2740",
      "title": "Metabolic biomarkers across the AD continuum: insights into how they maycontribute to neuropathology.",
      "parent_id": "S510",
      "starts_at": "2026-07-12T09:02:00+01:00",
      "ends_at": "2026-07-12T09:12:00+01:00",
      "location": "Victoria 5/6",
      "description_text": "Frederic Calon;\nUniversite Laval, Faculty of Pharmacy, Quebec, QC, Canada"
    }
  ]
}
```

The session CSV is a compact parent-session index. Daily presentation CSVs in
`data/aaic_2026/presentations_*.csv` are derived planning views.

When fetched with `--people`, `data/aaic_2026/people.json` is a map keyed by
EventPilot person id. Each record preserves the raw `speakers` table payload and
normalizes common fields such as name, degree, organization, city/state, and
country.

## Derived Exports

Daily presentation CSVs:

```bash
python3 scripts/export_presentations_by_date.py \
  --input data/aaic_2026/sessions.json \
  --outdir data/aaic_2026
```

SQLite:

```bash
python3 scripts/export_sqlite.py \
  --sessions data/aaic_2026/sessions.json \
  --people data/aaic_2026/people.json \
  --output data/aaic_2026/aaic_2026.sqlite
```

The SQLite export creates normalized `sessions`, `presentations`, `people`,
`session_people`, and `presentation_people` tables, plus an `agenda_items` view
that unions sessions and presentations for schedule search. If `people.json` is
missing, the exporter still creates placeholder people rows from ids referenced
by sessions and presentations.

See `STATUS.md` for current caveats and likely next modeling steps.

## Known Local Scratch Files

There are several probe files in the workspace from endpoint discovery:

- `planner.html`, `plantab_agenda.html`, `detail_S510.html`
- `EPUtility.js`, `EPFormat*.js`, `PlannerFilterFunctions.js`
- `agenda_*.txt`, `agenda_*.xml`, `autocomplete_*.txt`, `cookies*.txt`
- `aaic_sample/`

They are not required for normal use. The important files are:

- `scripts/scrape_aaic.py`
- `scripts/export_presentations_by_date.py`
- `scripts/export_sqlite.py`
- `README.md`
- `STATUS.md`
- `data/aaic_2026/sessions.json`
- `data/aaic_2026/people.json` if fetched with `--people`
- `data/aaic_2026/sessions.csv`
- `data/aaic_2026/presentations_*.csv`
- `data/aaic_2026/aaic_2026.sqlite` if exported

## Notes For Next Agent

- Network access may require escalation in the managed sandbox.
- The cookie expires; if requests start returning access errors, copy a fresh
  `Cookie:` header from the browser's Network tab.
- The app returns malformed or nested XML-ish responses. Avoid replacing the
  tolerant decoder with strict XML parsing unless the endpoint changes.
- Detail fetching uses conservative bounded concurrency. If the app starts
  returning likely limit errors, lower `--detail-workers` or increase
  `--detail-interval`.
