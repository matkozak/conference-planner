# Roadmap

Only unfinished work belongs here. Current architecture and normal commands are
documented in `README.md`.

## CTAD 2026

Publish a useful preliminary CTAD program well before the conference:

- [x] Save each acquired PDF unchanged under `data/ctad_2026/source/`.
- [x] Extract the program with `pdftohtml -xml`, plus `pdftocairo -svg` to
      recover the vector underline that marks each presenting author. The PDFs
      are InDesign exports whose typography carries the structure, so no OCR or
      VLM is needed.
- [x] Add a CTAD producer emitting a validated `ConferenceProgram` directly;
      the shared contract was not changed.
- [x] Keep honest positional session and symposium-presentation ids, and add a
      refresh-time identity review that checks every changed or removed item
      for attached notes and RSVPs.
- [x] Strengthen the review report to catch missing session bounds, uncurated
      chair lines, ambiguous presenters, and unmapped glyphs in descriptions.
- [ ] Review the extracted program against the PDFs before first publication,
      especially the sessions with no items and the synthetic locations.
- [x] Confirm the poster-session theme assignment against the CTAD website and
      preserve the source page under ignored `data/`; it is the only schedule
      input with no captured source document.
- [ ] Publish CTAD to R2, verify the production program and conference-scoped
      notebook, and advertise the planner.
- [ ] Re-run after CTAD fills in the late-breaking slots.

## Operational cleanup

- [ ] Publish the rewritten data-free history and rewritten tags to the chosen
      GitHub repository, then verify the remote before removing local backups.

## Small backlog

Do these only when there is a concrete need:

- Represent multi-day sessions so Poster Session 1 also appears in Tuesday
  browsing and day-scoped search.
- Search filters for sessions, talks, and posters.
- Include RSVPs in CSV exports.
