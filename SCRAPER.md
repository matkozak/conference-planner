# EventPilot scraper internals

This document preserves the reverse-engineered upstream protocol, normalization
decisions, and data quirks needed to maintain the scraper and its consumers. See
`README.md` for normal scrape, refresh, export, and verification commands.

## EventPilot protocol

The upstream API is not documented:

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

Responses are frequently an XML wrapper containing escaped XML, itself
containing escaped HTML cells. The scraper intentionally uses a tolerant decoder
rather than strict XML parsing. See `scripts/aaic_2026/scrape.py` for the exact form
fields, ordering, pagination, and normalization.

## Normalized data model

Each parent in `sessions.json` contains normalized fields such as `id`, date and
times, title, location, category, session number, descriptions, people ids, and
`subsession_ids`, plus embedded normalized `presentations`. People records are
keyed by EventPilot id and preserve the raw payload alongside common normalized
name and affiliation fields.

JSON remains lossless and authoritative. Full author/affiliation blocks stay in
`description_html` and `description_text`. EventPilot exposes only primary
people ids separately, and the current planning use case does not justify
parsing every author into rows.

The SQLite exporter creates normalized `sessions`, `presentations`, `people`,
`session_people`, and `presentation_people` tables, plus an `agenda_items` union
view. It retains lossless HTML descriptions but omits duplicate plain text and
raw source records. If `people.json` is absent, it creates placeholder people
rows for referenced ids.

## Current upstream quirks

- EventPilot presentation order is unreliable in 128 of 363 sessions. The dump
  preserves it; the AAIC app adapter sorts presentations by start time.
- Poster data currently has 5,731 concrete board-number locations, 117 generic
  `Exhibit Hall` locations, and 19 literal `Board no. #N/A` values.
- The four Plenary parents have no EventPilot child records. Their descriptions
  could support explicitly marked derived presentation rows if that ever becomes
  useful, but the scraper does not invent them.

## Downstream app contract

The conference app's `scripts/providers/eventpilot-aaic.ts` adapter consumes
`id`, `date`, times, title, location, category, session number, speaker ids,
descriptions, and embedded presentations. Coordinate any source-data shape
change with that adapter.

The adapter keeps the nested presentation shape, intentionally omits relational
hints such as `parent_id` and `subsession_ids`, adds conference metadata and
normalized item kinds, and validates the result as `ConferenceProgram` v1 before
the builder writes an R2 publication candidate. See `schema/README.md` for the
portable contract and publication invariants.
