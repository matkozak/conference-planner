# Project Status

## What Exists

- `scripts/scrape_aaic.py`: standard-library scraper for the AAIC 2026 EventPilot planner.
- `data/aaic_2026/sessions.json`: full current dump.
- `data/aaic_2026/sessions.csv`: session-level CSV derived from the JSON dump.

The current dump contains:

- 360 parent sessions
- 360 parsed locations
- 6,850 nested presentations
- 0 detail fetch errors from the completed run

## Known Flattening / Lossy Shapes

The JSON is the richer source of truth. The CSV is intentionally flattened for
quick scanning.

Current flattened fields:

- `sessions.csv` has one row per parent session, not one row per presentation.
- `presentation_titles` is a ` | `-delimited list of nested presentation titles.
- `presentation_count` is derived from the JSON presentations array.
- Each presentation in JSON currently has `time_and_speaker`, a scraper-created
  flattened string from the parent session detail page. It combines presentation
  time and display speaker, for example:
  `8:02am-8:09am Jul 15 (BST) Mark Kindy`.
- Parent `speakers_summary` is the app's comma-separated display string.
- Parent `speakers` is structured as an array of `{name, affiliation}` objects
  parsed from detail pages.

Presentation detail pages can expose more structure than the current nested
presentation objects keep:

- presentation title
- presentation time
- location
- display speaker/presenter via `speaker_cell`
- speaker affiliation
- author line and superscript affiliations in the detail description

The current scraper does not fetch every `P...` presentation detail page, so it
does not yet preserve full presentation authors/affiliations.

## Likely Next Steps

- Generate `data/aaic_2026/presentations.csv` with one row per presentation,
  including parent session id/title/category/location.
- Split `time_and_speaker` into presentation `starts_at`, `ends_at`, and
  `speaker_display`.
- Normalize times into UTC ISO-8601 strings for storage/search.
- Consider a SQLite export:
  - `sessions`
  - `presentations`
  - optionally `speakers` and join tables
  - optionally a view that unions sessions and presentations as schedulable
    agenda items.
- If full author lists matter, extend the scraper to fetch each presentation
  detail page and parse author/affiliation blocks.

## Operational Notes

- The scraper requires a fresh logged-in `Cookie:` header as `AAIC_COOKIE` or
  `--cookie`.
- Network requests may need approval in the managed sandbox.
- EventPilot API responses are malformed/nested XML-ish wrappers. Keep the
  tolerant parser unless the endpoint format changes.
