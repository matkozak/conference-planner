# Project Status

## What Exists

- `scripts/scrape_aaic.py`: standard-library scraper for the AAIC 2026 EventPilot planner.
- `scripts/export_presentations_by_date.py`: derived daily planning CSV exporter.
- `scripts/export_sqlite.py`: normalized SQLite exporter for the JSON dump.
- `data/aaic_2026/sessions.json`: full current structured dump.
- `data/aaic_2026/sessions.csv`: compact parent-session CSV index.
- `data/aaic_2026/presentations_*.csv`: one planning CSV per date.

The current structured dump contains:

- 360 parent sessions
- 360 parent sessions with locations
- 106 parent sessions with description text
- 6,850 nested presentations
- 6,699 nested presentations with description text
- 0 parent or presentation detail fetch errors from the completed run

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

## People Roadmap

The scraper can now fetch EventPilot `speakers` table records with `--people`
and writes them to `people.json`, keyed by person id. The normalizer lifts common
fields such as first name, last name, full name, organization, degree, city,
state, country, and profile HTML while preserving the raw EventPilot payload.

Remaining modeling choices:

- Keep presentation `description_html` and `description_text` as the full
  author/affiliation source, because EventPilot's speaker ids usually identify
  the primary presenter rather than every author.
- Defer parsing full author lists into structured author rows until it is clear
  that the formatting is consistent enough to trust.

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

## Operational Notes

- The scraper requires a fresh logged-in `Cookie:` header as `AAIC_COOKIE` or
  `--cookie`.
- Network requests may need approval in the managed sandbox.
- EventPilot API responses are malformed/nested XML-ish wrappers. Keep the
  tolerant parser unless the endpoint format changes.
- Detail fetching uses bounded concurrency. If the app starts returning likely
  limit errors, lower `--detail-workers` or increase `--detail-interval`.
