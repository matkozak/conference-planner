# Conference planner repository

This repository contains two deliberately separate systems:

1. Source-specific ingestion tools build immutable conference programs.
2. A TypeScript Cloudflare Worker app lets a small internal team browse those
   programs, RSVP, and share notes.

The app is multi-conference. AAIC 2026 uses the mature Python EventPilot
scrape plus an adapter; CTAD 2026 uses a separate Python PDF extraction
pipeline that produces a schema-conformant program directly.

## Boundaries

- Real conference sources and extraction artifacts live under ignored `data/`.
- Small synthetic fixtures used by tests stay in Git.
- Every producer must hand the app a validated, provider-independent
  `ConferenceProgram`; raw provider shapes never cross into runtime code.
- Program data is immutable to the app and published separately from Worker
  deployment.
- Private R2 stores the conference catalog and immutable programs.
- One SQLite-backed Durable Object per conference stores mutable notes and
  RSVPs.
- Cloudflare Access is the only production authentication boundary. The Worker
  validates the JWT signature, issuer, and audience before using its email
  claim as identity.

## Layout

- `app/` — Svelte frontend, Worker, shared TypeScript, adapters, and publisher
- `app/.programs/` — ignored validated publication candidates
- `scripts/<conference_year>/` — source-specific ingestion packages
- `data/<conference_year>/` — ignored local source and working data
- `tests/` — Python ingestion and integrity tests
- `schema/` — portable program schema and invariants
- `ROADMAP.md` — unfinished work only

Per-conference protocol and operating instructions live in
`scripts/aaic_2026/README.md` and `scripts/ctad_2026/README.md`.

## Commands

Python is standard-library only:

```bash
python3 -m unittest
```

CTAD ingestion additionally needs `pdftohtml` and `pdftocairo` from
poppler-utils:

```bash
python3 -m scripts.ctad_2026.build            # build the CTAD candidate
python3 -m scripts.ctad_2026.build --report   # review without writing
```

Run app commands from `app/` with pnpm. With the repository mise environment
active, they also work from the repository root because `PNPM_CONFIG_DIR`
points at `app/`:

```bash
pnpm install      # install pinned dependencies
pnpm run aaic:build  # build the current AAIC publication candidate
pnpm run program:check <program.json>    # validate a candidate
pnpm run program:publish <program.json>  # publish a candidate to R2
pnpm run ctad:build    # build and fully verify the CTAD candidate
pnpm run ctad:publish  # reconcile, publish, and verify CTAD production
pnpm run check    # Svelte and TypeScript checks
pnpm run test     # Vitest
pnpm run dev      # Vite with the Worker running in workerd
pnpm run build    # production build
pnpm run deploy   # build and deploy
pnpm run types    # regenerate Worker declarations after wrangler changes
```

## Practices

- KISS and YAGNI. Prefer direct code over speculative frameworks.
- Functions do things; classes store data, except where the platform requires a
  class shape such as Durable Objects.
- TypeScript is strict. Shared API and domain types live in `app/src/shared/`
  and are never duplicated across the Worker/frontend boundary.
- Keep dependencies minimal and mature. The Python ingestion side remains
  standard-library only.
- Use pnpm only. Its lockfile is `app/pnpm-lock.yaml`; dependency build scripts
  are allowlisted in `app/package.json`.
- Never commit secrets, cookies, real conference data, or notebook snapshots.
  EventPilot authentication comes from `AAIC_COOKIE`.

## Verification

Before completing an app change, run `pnpm run check` and `pnpm run test` from
`app/`. For Python ingestion or data changes, run `python3 -m unittest` from the
repository root.
