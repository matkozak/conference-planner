# AAIC 2026 — scraper + conference app

Two things live here:

1. **Scraper & data pipeline** (Python, stdlib only) — scrapes the AAIC 2026
   EventPilot planner into `data/aaic_2026/`. Complete and integrity-tested.
   See `README.md` for endpoints and rerun instructions.
2. **Conference app** (`app/`, TypeScript, Cloudflare Worker) — a better
   conference app for ~10 internal users at `aaic2026.kozak.ch`.
   See `ROADMAP.md` for architecture and milestones.

The scraped data is **immutable**: refreshed only by deliberate scraper reruns,
never mutated by the app.

## Layout

- `scripts/` — Python scraper + exporters (stdlib only, keep it that way)
- `data/aaic_2026/` — the committed dump (JSON is source of truth)
- `tests/` — Python data-integrity tests
- `app/` — the Worker app (own `package.json`, everything TS)
- `STATUS.md` — data-side status and caveats
- `ROADMAP.md` — app-side architecture decisions and milestones

## Commands

Data side (Python 3, `.venv` exists but stdlib suffices):

```bash
python3 -m unittest tests.test_data_integrity   # verify the dump
```

App side (Node LTS via mise, run from `app/`):

```bash
npm run check    # typecheck (svelte-check + tsc) — run before declaring done
npm run test     # vitest
npm run dev      # wrangler dev
npm run deploy   # wrangler deploy
```

## Practices

- Grug brained: KISS, YAGNI. No forced abstractions, no enterprise patterns.
  Functions do things, classes store data (Durable Object classes excepted —
  that's the platform's shape).
- TypeScript `strict` everywhere. Shared API/domain types live in
  `app/src/shared/` and are imported by both Worker and frontend — never
  duplicate a type across that boundary.
- Dependencies: minimal and mature. Justify each new one in the PR/commit.
- Identity comes from Cloudflare Access headers; the app has **no auth code**
  of its own beyond reading the verified email.
- Secrets/cookies never committed. The EventPilot cookie comes from
  `AAIC_COOKIE` env only.

## Verification

Before considering any app change done: `npm run check` and `npm run test`
from `app/` must pass. For data changes: the unittest above must pass.
