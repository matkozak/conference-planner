# Conference app and AAIC 2026 program data

This repository contains two deliberately separate pieces:

1. A Python standard-library scraper and export pipeline for the AAIC 2026
   EventPilot planner. Its committed JSON dump is the source of truth.
2. A small multi-conference internal app deployed at
   [conferences.kozak.ch](https://conferences.kozak.ch), implemented as a
   Cloudflare Worker with a Svelte frontend and conference-scoped Durable Object
   notebooks.

The app never changes the scraped program. Program refreshes are explicit,
reviewed operations performed by the scraper tooling.

The production root lists the conference catalog;
`conferences.kozak.ch/aaic-2026/` opens AAIC directly. The historical
`aaic2026.kozak.ch` hostname temporarily remains as a compatibility alias whose
root loads AAIC directly.

## Current data

`data/aaic_2026/` contains the July 10 refresh:

| Metric                         | Count |
| ------------------------------ | ----: |
| Parent sessions                |   363 |
| Parent sessions with locations |   361 |
| Nested presentations           | 7,915 |
| People                         | 6,105 |
| Detail or people fetch errors  |     0 |

The committed files are:

- `sessions.json` and `people.json`: source-of-truth scraped data.
- `sessions.csv`: compact parent-session index (364 lines with its header).
- `presentations_*.csv`: derived daily planning views.
- `aaic_2026.sqlite`: derived normalized database.

The integrity suite verifies people references, parent/child relationships,
categories, duplicate ids, description coverage, and SQLite row counts and
foreign keys.

## Controlled program refresh

Never scrape directly into `data/aaic_2026/`. The refresh helper stages a full
candidate under ignored `.refresh/`, validates it, compares program ids and
content, and checks removals against a fresh snapshot of notebook notes and
RSVPs.

`AAIC_COOKIE` must contain a current logged-in EventPilot cookie. It can be
provided by the ignored local mise configuration; never commit or hard-code it.

Prepare a candidate:

```bash
python3 -m scripts.refresh_aaic prepare
```

The command prints its staging path and the exact eventual `apply` command. If
the scrape is interrupted, resume that same directory:

```bash
python3 -m scripts.refresh_aaic prepare \
  --stage ".refresh/{timestamp}" --resume
```

Inspect an existing candidate again:

```bash
python3 -m scripts.refresh_aaic inspect ".refresh/{timestamp}"
```

Each inspection fetches a fresh notebook snapshot through Cloudflare Access.
When its session has expired, `cloudflared` opens the normal browser login flow.
For offline recovery or tests, `--notebook-snapshot PATH` replaces that fetch.

Review the generated `report.md` before promotion. Structural validation errors,
possible id reuse, and removed ids referenced by notes or RSVPs block promotion.
Unreferenced removals remain visible for review but do not block. A deliberate
removal or reuse can be acknowledged per id with `--allow-id-change ID`; this
does not migrate notebook references.

Promote an unchanged, reviewed candidate:

```bash
python3 -m scripts.refresh_aaic apply ".refresh/{timestamp}"
```

`apply` rechecks candidate and baseline hashes, fetches the notebook immediately
before its final blocker check, promotes files atomically, and regenerates the
CSV and SQLite exports. It never publishes program data or deploys the app.

Build the validated, ignored publication candidate separately:

```bash
cd app
pnpm run program
```

This runs the AAIC/EventPilot adapter and writes
`.programs/aaic-2026.json`. The scraper dump remains the lossless AAIC source;
the provider-independent `ConferenceProgram` is the application's input
boundary.

Publish only after reviewing that candidate. The publisher requires a
bucket-scoped R2 access key in `R2_ACCESS_KEY_ID` and
`R2_SECRET_ACCESS_KEY`, plus `R2_ACCOUNT_ID`; `R2_BUCKET` defaults to
`conference-programs`.

```bash
pnpm run program:publish -- .programs/aaic-2026.json
```

Publication validates the program again and reads the current catalog. An
unchanged program verifies its existing immutable object and exits without
rewriting the catalog. A changed program uploads and reads back its
full-SHA-256 object, then conditionally updates `catalog.json` against the R2
ETag. A concurrent promotion fails without changing the catalog pointer.
Program publication does not build or deploy the Worker.

Controlled refreshes default to four agenda-detail workers with a 0.20-second
request-start interval, and four people workers with a 0.05-second interval.
Lower concurrency or increase the interval if EventPilot begins rate-limiting.

## Direct scraper use

`scripts/scrape_aaic.py` is useful for smoke tests and resuming low-level work.
It uses only the Python standard library.

```bash
AAIC_COOKIE='...' python3 scripts/scrape_aaic.py \
  --date 2026-07-12 --max-sessions 2 --outdir aaic_sample
```

Important options:

- `--resume`: preserve completed session, presentation, and person records and
  retry missing or failed details.
- `--date YYYY-MM-DD`: restrict the scrape to one date; repeatable.
- `--max-sessions N`: limit a validation run.
- `--no-details`: fetch only parent-session lists.
- `--people`: fetch referenced EventPilot `speakers` records into `people.json`.
- `--detail-workers`, `--detail-interval`, `--people-workers`, and
  `--people-interval`: bound request concurrency and pacing.
- `--save-every` and `--log-every`: control checkpoints and progress logging.

Copy the cookie from a logged-in browser request to
`https://eppro01.ativ.me/web/api.php`. The scraper also accepts `--cookie`, but
the environment variable avoids leaving credentials in shell history.

## Derived exports

Regenerate daily CSVs:

```bash
python3 scripts/export_presentations_by_date.py \
  --input data/aaic_2026/sessions.json \
  --people data/aaic_2026/people.json \
  --outdir data/aaic_2026
```

Regenerate SQLite:

```bash
python3 scripts/export_sqlite.py \
  --sessions data/aaic_2026/sessions.json \
  --people data/aaic_2026/people.json \
  --output data/aaic_2026/aaic_2026.sqlite
```

## Verification

Run the complete Python suite after scraper, refresh, or data changes:

```bash
python3 -m unittest
```

For the reverse-engineered API, normalized data model, and upstream quirks, see
`SCRAPER.md`. For app architecture and open work, see `ROADMAP.md`. Contributor
and agent conventions live in `AGENTS.md` (`CLAUDE.md` is its source file).
