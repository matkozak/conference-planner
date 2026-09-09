# Conference planner

This repository contains a small private web app for planning conference
attendance. Team members can browse a program, search sessions and
presentations, RSVP, share notes, and view personal or team schedules.

The app currently serves AAIC 2026 and is designed to accept other conferences
without teaching the frontend about each source format. CTAD 2026 is next.

## How it fits together

Conference programs are built outside the running app:

```text
local source or scrape
  -> source-specific extraction
  -> validated ConferenceProgram JSON
  -> private R2 storage
  -> conference app
```

Real conference source material and extraction work live in the ignored local
`data/` directory. Validated publication candidates are written to the ignored
`app/.programs/` directory. Small synthetic fixtures remain in Git for tests.

The deployed app is one Cloudflare Worker:

- Svelte provides the browser interface.
- Hono routes the API.
- Private R2 stores immutable conference programs and the conference catalog.
- One SQLite-backed Durable Object per conference stores notes and RSVPs.
- Cloudflare Access protects production and supplies the user's identity.

Programs use the provider-independent `ConferenceProgram` contract in
`app/src/shared/program.ts`. Source-specific code may change freely on its side
of that boundary; the browser and Worker never consume raw scraper or
extraction formats.

## Repository layout

- `app/` — Svelte frontend, Worker, shared TypeScript, program adapters, and
  publishing tools
- `scripts/` — source-specific Python ingestion tools
- `data/` — ignored local source files, extraction work, and derived data
- `tests/` — Python ingestion and data-integrity tests
- `schema/` — portable `ConferenceProgram` schema and invariant notes
- `ROADMAP.md` — unfinished work only

AAIC's scraper, refresh workflow, upstream protocol notes, and commands live in
[`scripts/aaic_2026/README.md`](scripts/aaic_2026/README.md).

## Useful commands

Run the Python suite from the repository root:

```bash
python3 -m unittest
```

Run app commands from `app/` using pnpm:

```bash
pnpm install      # install pinned dependencies
pnpm run check    # Svelte and TypeScript checks
pnpm run test     # Vitest
pnpm run dev      # local Vite/workerd development
pnpm run build    # production build
pnpm run deploy   # build and deploy the Worker
pnpm run types    # regenerate Worker types after wrangler config changes
```

Build the current AAIC source into a validated publication candidate:

```bash
cd app
pnpm run aaic:build
```

Publish a reviewed candidate independently of an app deployment:

```bash
pnpm run program:publish .programs/aaic-2026.json
```

Publishing requires the bucket-scoped R2 credentials documented in the AAIC
ingestion README. Program publication and Worker deployment are deliberately
separate operations. Run one publication at a time: catalog updates are
unconditional, so overlapping publishes can overwrite each other’s changes.
