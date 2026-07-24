# AAIC 2026 ingestion

This package maintains the AAIC 2026 EventPilot scrape. It stages and reviews
refreshes, keeps a lossless provider-oriented JSON representation, produces
optional CSV and SQLite views, and hands the source data to the app's AAIC
adapter.

Real data lives under the ignored local `data/aaic_2026/` directory:

- `sessions.json` and `people.json` are the ingestion source of truth.
- `sessions.csv`, `presentations_*.csv`, and `aaic_2026.sqlite` are derived.
- `refreshes/<timestamp>/` contains staged refresh candidates and reports.
- `scratch/` is suitable for small direct scraper runs.

The app does not mutate these files.

## Controlled refresh

Never scrape directly over the current dataset. The refresh command stages a
complete candidate, validates it, compares item identity and content, and
checks removals against a fresh snapshot of notebook notes and RSVPs.

`AAIC_COOKIE` must contain a current logged-in EventPilot cookie. It may be
provided through the ignored local mise configuration; never commit or
hard-code it.

Prepare a candidate:

```bash
python3 -m scripts.aaic_2026.refresh prepare
```

Resume an interrupted candidate:

```bash
python3 -m scripts.aaic_2026.refresh prepare \
  --stage "data/aaic_2026/refreshes/{timestamp}" --resume
```

Inspect it again:

```bash
python3 -m scripts.aaic_2026.refresh inspect \
  "data/aaic_2026/refreshes/{timestamp}"
```

Review `report.md`, then promote the unchanged candidate:

```bash
python3 -m scripts.aaic_2026.refresh apply \
  "data/aaic_2026/refreshes/{timestamp}"
```

Structural errors, possible ID reuse, and removed IDs referenced by notes or
RSVPs block promotion. A deliberate removal or reuse can be acknowledged with
`--allow-id-change ID`; this does not migrate notebook references.

`apply` rechecks the candidate and baseline hashes, fetches the notebook again,
promotes files atomically, and regenerates the derived exports. It does not
publish to R2 or deploy the app.

## Direct scraper and exports

The low-level scraper requires an explicit output directory:

```bash
AAIC_COOKIE='...' python3 -m scripts.aaic_2026.scrape \
  --date 2026-07-12 --max-sessions 2 \
  --outdir data/aaic_2026/scratch
```

Useful options include:

- `--resume` to preserve complete records and retry missing or failed details
- repeatable `--date YYYY-MM-DD` filters
- `--no-details` for parent-session lists only
- `--people` to fetch referenced speaker records
- worker and interval options for bounded concurrency and pacing
- `--save-every` and `--log-every` for checkpoints and progress

The cookie can also be passed with `--cookie`, but the environment avoids shell
history. Copy it from a logged-in request to
`https://eppro01.ativ.me/web/api.php`.

Regenerate the derived files from the current local dataset:

```bash
python3 -m scripts.aaic_2026.export_presentations
python3 -m scripts.aaic_2026.export_sqlite
```

## EventPilot protocol

The upstream API is undocumented:

- Planner shell:
  `https://eppro01.ativ.me/src/EventPilot/php/express/web/planner.php?id=ALZ19292F861B994564D`
- Program iframe:
  `https://eppro01.ativ.me/web/plantab.php?id=ALZ19292F861B994564D&plannersession=true&tab=urn%3Aeventpilot%3Aplanner%3Aagenda%3A%3A`
- API endpoint: `POST https://eppro01.ativ.me/web/api.php`
- Parent lists use `interface=webfilter`, `action=getlist`, `table=agenda`, an
  empty `parent` filter, and a date filter.
- Details use `interface=eptable`, `action=gettabledata`, `table=agenda`, and
  `tid=<ITEM_ID>`.
- People use the same table-data interface with `table=speakers`.

Responses are often an XML wrapper containing escaped XML, itself containing
escaped HTML cells. `scrape.py` intentionally uses a tolerant decoder rather
than strict XML parsing.

## Provider data and quirks

Each parent in `sessions.json` contains normalized dates, times, titles,
locations, categories, descriptions, people IDs, and embedded presentations.
People are keyed by EventPilot ID and retain the upstream payload alongside
normalized names and affiliations.

Full author and affiliation blocks remain in `description_html` and
`description_text`. EventPilot exposes only primary people separately, and the
planning app does not need every author normalized into rows.

Known quirks:

- Presentation order is unreliable; the app adapter sorts by start time.
- Poster locations include real board numbers, generic `Exhibit Hall` values,
  and literal `Board no. #N/A` values.
- Plenary parents have no EventPilot child records. The scraper does not invent
  presentations from their descriptions.

The SQLite exporter creates normalized session, presentation, people, and link
tables plus an `agenda_items` view. It is a derived inspection format, not an
application database.

## App handoff and verification

`app/scripts/providers/eventpilot-aaic.ts` maps this provider shape to the
stable `ConferenceProgram` contract. Coordinate changes to IDs, dates, times,
descriptions, people, or embedded presentations with that adapter.

Run the Python integrity and refresh tests:

```bash
python3 -m unittest
```

Build and validate the app-side candidate:

```bash
cd app
pnpm run program
pnpm run check
pnpm run test
```

The builder writes `.programs/aaic-2026.json`. After reviewing it, publish with
bucket-scoped `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_ACCOUNT_ID`;
`R2_BUCKET` defaults to `conference-programs`:

```bash
pnpm run program:publish -- .programs/aaic-2026.json
```

The publisher validates the program, uploads and reads back its immutable
full-SHA-256 object, and updates `catalog.json` with an ETag concurrency guard.
