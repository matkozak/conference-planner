# Roadmap

Only unfinished work belongs here. Current architecture and normal commands are
documented in `README.md`.

## CTAD 2026

Publish a useful preliminary CTAD program well before the conference:

- [ ] Save each acquired PDF unchanged under `data/ctad_2026/source/`.
- [ ] Inspect the document and start with the simplest reliable extraction,
      preferably `pdftotext`; add OCR or VLM assistance only where needed.
- [ ] Choose stable session and presentation IDs before users can create notes
      or RSVPs. Do not derive identity solely from editable titles.
- [ ] Produce reviewed CTAD-specific structured data under
      `data/ctad_2026/extracted/`.
- [ ] Add a CTAD producer or adapter that emits a validated
      `ConferenceProgram`. Change the shared contract only for genuine
      cross-conference concepts, never PDF quirks.
- [ ] Publish CTAD to R2, verify the production program and conference-scoped
      notebook, and advertise the planner.

## Operational cleanup

- [ ] Publish the rewritten data-free history and rewritten tags to the chosen
      GitHub repository, then verify the remote before removing local backups.
- [ ] After the compatibility window, retire `aaic2026.kozak.ch`: remove the
      Worker route, Access application, legacy-host code, and tests; deploy and
      verify Cloudflare removed its managed DNS record.

## Small backlog

Do these only when there is a concrete need:

- Search filters for sessions, talks, and posters.
- Include RSVPs in CSV exports.
- Re-enable pnpm's `verifyDepsBeforeRun` after its upstream crash is fixed; see
  `app/pnpm-workspace.yaml`.
