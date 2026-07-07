# Project Status

## What Exists

- `scripts/scrape_aaic.py`: standard-library scraper for the AAIC 2026 EventPilot planner.
- `scripts/export_presentations_by_date.py`: derived daily planning CSV exporter.
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

## Remaining Modeling Choices

- Decide whether to parse `description_html` into structured authors and
  affiliations, or keep it as a single author/affiliation text field.
- Consider a SQLite export:
  - `sessions`
  - `presentations`
  - optionally `people`
  - optionally a view that unions sessions and presentations as schedulable
    agenda items.
- Decide whether poster board numbers should remain in `location` or also be
  split into a dedicated board field.

## Operational Notes

- The scraper requires a fresh logged-in `Cookie:` header as `AAIC_COOKIE` or
  `--cookie`.
- Network requests may need approval in the managed sandbox.
- EventPilot API responses are malformed/nested XML-ish wrappers. Keep the
  tolerant parser unless the endpoint format changes.
- Detail fetching uses bounded concurrency. If the app starts returning likely
  limit errors, lower `--detail-workers` or increase `--detail-interval`.
