# Conference planner repository

This repository contains the TypeScript Cloudflare Worker app and the generic
publication boundary for provider-independent conference programs.

Conference-specific scrapers, parsers, source files, corrections, and ingestion
tests live in
[`matkozak/conference-program-producers`](https://github.com/matkozak/conference-program-producers).
That repository hands this app a validated `ConferenceProgram` JSON document;
raw provider shapes never enter runtime or publication code.

## Boundaries

- `schema/` defines the portable producer contract and invariants.
- `app/fixtures/` contains small synthetic fixtures only.
- `app/.programs/` is ignored workspace for local publication candidates.
- Program data is immutable and published separately from Worker deployment.
- Private R2 stores the conference catalog and immutable programs.
- One SQLite-backed Durable Object per conference stores mutable notes and
  RSVPs.
- Cloudflare Access is the only production authentication boundary.
- Every update is reviewed against the published baseline and a fresh notebook
  snapshot before publication.

## Layout

- `app/` — Svelte frontend, Worker, shared TypeScript, and publisher
- `schema/` — portable program schema, example, and producer instructions
- `ROADMAP.md` — unfinished app and publication-boundary work only

## Commands

Run app commands from `app/` with pnpm. With the repository mise environment
active, they also work from the repository root because `PNPM_CONFIG_DIR`
points at `app/`:

```bash
pnpm install
pnpm run program:check <program.json>
pnpm run program:review <program.json>
pnpm run program:publish <program.json>
pnpm run check
pnpm run test
pnpm run dev
pnpm run build
pnpm run deploy
pnpm run types
```

## Practices

- KISS and YAGNI. Prefer direct code over speculative frameworks.
- Functions do things; classes store data, except where the platform requires a
  class shape such as Durable Objects.
- TypeScript is strict. Shared API and domain types live in `app/src/shared/`
  and are never duplicated across the Worker/frontend boundary.
- Keep dependencies minimal and mature.
- Use pnpm only. Its lockfile is `app/pnpm-lock.yaml`; dependency build scripts
  are allowlisted in `app/package.json`.
- Never commit secrets, real conference data, notebook snapshots, or generated
  publication candidates.

## Verification

Before completing a change, run `pnpm run check` and `pnpm run test` from
`app/`.
