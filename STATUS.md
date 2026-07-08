# Project Status

## What Exists

- `scripts/scrape_aaic.py`: standard-library scraper for the AAIC 2026 EventPilot planner.
- `scripts/export_presentations_by_date.py`: derived daily planning CSV exporter,
  including parent session category for downstream filtering and presenter names
  resolved from `people.json`.
- `scripts/export_sqlite.py`: normalized SQLite exporter for the JSON dump.
- `tests/test_data_integrity.py`: JSON/SQLite consistency tests for the committed dump.
- `data/aaic_2026/sessions.json`: full current structured dump.
- `data/aaic_2026/people.json`: fetched EventPilot `speakers` records keyed by person id.
- `data/aaic_2026/sessions.csv`: compact parent-session CSV index.
- `data/aaic_2026/presentations_*.csv`: one planning CSV per date.
- `data/aaic_2026/aaic_2026.sqlite`: normalized SQLite export.

The current structured dump contains:

- 360 parent sessions
- 360 parent sessions with locations
- 106 parent sessions with description text
- 6,850 nested presentations
- 6,699 nested presentations with description text
- 5,217 people records
- 0 parent or presentation detail fetch errors from the completed run
- 0 people fetch errors

Current integrity checks pass:

- All referenced `speaker_ids`/`person_ids` have matching `people.json` records.
- In the current dump, `speaker_ids` and `person_ids` are identical for every
  session and presentation.
- Parent `subsession_ids` exactly match embedded presentation ids.
- Embedded presentation `parent_id` values match their containing parent
  session.
- Embedded presentation `category` and `category_id` values match their
  containing parent session.
- SQLite row counts and foreign keys match the JSON source.

## Current Shape

The JSON is the source of truth. Parent sessions and nested presentations use the
same core fields where EventPilot provides them:

- `id`
- `parent_id`
- `date`
- `starts_at`
- `ends_at`
- `title`
- `description_html`
- `description_text`
- `location`
- `category`
- `category_id`
- `session_number`
- `speaker_ids`
- `person_ids`
- `subsession_ids`
- `media`
- `metadata`
- `related_ids`
- `related_scores`

Parent sessions additionally contain `presentations`, a list of normalized
presentation objects. Presentation author and affiliation blocks are preserved in
`description_html` and `description_text`; EventPilot only exposes primary
speaker/person ids separately.

## People Data

The scraper can now fetch EventPilot `speakers` table records with `--people`
and writes them to `people.json`, keyed by person id. The normalizer lifts common
fields such as first name, last name, full name, organization, degree, city,
state, country, and profile HTML while preserving the raw EventPilot payload.

Author/affiliation blocks are intentionally not parsed into structured rows for
now. They are preserved in presentation `description_html` and
`description_text`; full author-list modeling is low value for the current
planning use case.

## Plenary Notes

The four actual plenary parent sessions have `category == "Plenary"` and no
EventPilot child presentation records. Their `description_text` is consistently
structured enough to derive one or two plenary presentation rows from lines that
begin `Plenary Presentation - ...`, followed by a `Speakers:` block.

This should be modeled, if needed, as post-processing with clearly marked
derived rows rather than as scraped EventPilot `subsession_ids`.

## SQLite Export

`scripts/export_sqlite.py` exports the JSON dump to a small normalized schema:

- `sessions`: parent agenda rows where `parent_id` is empty.
- `presentations`: child agenda rows with `parent_session_id`.
- `people`: records fetched from EventPilot's `speakers` table.
- `session_people` and `presentation_people`: join tables for referenced
  `speaker_ids` and `person_ids`, with a simple `role` value of `speaker` or
  `person`.
- `agenda_items`: a view that unions sessions and presentations for schedule
  search.

If `people.json` has not been fetched, the exporter creates placeholder `people`
rows for every referenced id so joins and foreign keys remain valid.

Other modeling choices to settle:

- Whether to keep EventPilot's `subsession_ids` only in raw JSON, since
  `presentations.parent_session_id` is enough for normalized SQLite.
- Whether poster board numbers should remain in `location` or also be split into
  a dedicated board field.
- Whether to derive plenary presentation rows from plenary description text.

## Operational Notes

- The scraper requires a fresh logged-in `Cookie:` header as `AAIC_COOKIE` or
  `--cookie`.
- Network requests may need approval in the managed sandbox.
- EventPilot API responses are malformed/nested XML-ish wrappers. Keep the
  tolerant parser unless the endpoint format changes.
- Detail fetching uses bounded concurrency. If the app starts returning likely
  limit errors, lower `--detail-workers` or increase `--detail-interval`.
