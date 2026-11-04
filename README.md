# Conference planner

This repository contains a small private web app for planning conference
attendance and the publication boundary that supplies its data. Team members
can browse programs, search sessions and presentations, RSVP, share notes, and
view personal or team schedules.

Conference-specific acquisition and extraction live in separate producer
projects. This repository accepts only a provider-independent,
schema-conformant `ConferenceProgram` JSON document:

```text
external producer
  -> ConferenceProgram JSON
  -> contract validation
  -> production identity and notebook review
  -> immutable R2 object + catalog promotion
  -> conference app
```

No conference source documents, scrapers, provider adapters, or generated
publication candidates belong in this repository.

## Repository layout

- `app/` — Svelte frontend, Worker, shared domain types, and publication tools
- `app/.programs/` — ignored local publication candidates
- `schema/` — portable JSON Schema, producer contract, and example program
- `ROADMAP.md` — unfinished app work only

The deployed app is one Cloudflare Worker. Private R2 stores the immutable
programs and small catalog. One SQLite-backed Durable Object per conference
stores mutable notes and RSVPs. Cloudflare Access protects production and
supplies the user's identity.

## Producer contract

A producer owns source acquisition, parsing, corrections, and stable item
identity. Its only handoff is one complete `ConferenceProgram` JSON document.
See [`schema/README.md`](schema/README.md), the generated JSON Schema, and the
synthetic example in `app/fixtures/synthetic-program.json`.

Validate a candidate without production access:

```bash
pnpm run program:check /path/to/program.json
```

Review it against the current published program and a fresh notebook snapshot:

```bash
pnpm run program:review /path/to/program.json
```

The review always blocks possible item-ID reuse and removal of an item carrying
notes or RSVPs. A reviewed, non-identity content change on a referenced item
can be acknowledged explicitly:

```bash
pnpm run program:review /path/to/program.json \
  --allow-content-change ITEM_ID
```

Review uses `cloudflared access curl`; `CONFERENCE_APP_URL` may override the
default production origin `https://conferences.kozak.ch`.

## Publishing

Publication repeats the production review before writing. It uploads the
validated program under its full SHA-256 digest, verifies the immutable object,
and replaces only that conference's catalog entry. It refuses to continue if
the catalog changed after review.

Set bucket-scoped `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and
`R2_SECRET_ACCESS_KEY`; `R2_BUCKET` defaults to `conference-programs`:

```bash
pnpm run program:publish /path/to/program.json
```

Pass `--allow-content-change ITEM_ID` to publication when the same explicit
acknowledgment was appropriate during review. Run one publisher at a time:
catalog promotion is a single whole-object write.

Program publication and Worker deployment are deliberately separate.

## Development

Use the repository mise environment, then run app commands from the repository
root or `app/`:

```bash
mise install
pnpm install
pnpm run check
pnpm run test
pnpm run dev
pnpm run build
pnpm run deploy
```

Local Worker development reads the real private program catalog through the
remote R2 binding. Its Durable Object is local, so development notes and RSVPs
start separately from production.
