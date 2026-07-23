# AAIC 2026 scraper + multi-conference app

Two things live here:

1. **Scraper & data pipeline** (Python, stdlib only) — scrapes the AAIC 2026
   EventPilot planner into the ignored local `data/aaic_2026/` workspace.
   Complete and integrity-tested.
   See `README.md` for endpoints and rerun instructions.
2. **Conference app** (`app/`, TypeScript, Cloudflare Worker) — a
   multi-conference app for ~10 internal users, currently deployed for AAIC at
   `aaic2026.kozak.ch`.
   See `ROADMAP.md` for current architecture and open work.

The scraped data is **immutable to the app**: refreshed only through the
deliberate scraper pipeline, never mutated at runtime.

## Layout

- `scripts/` — Python scraper + exporters (stdlib only, keep it that way)
- `data/` — ignored local conference sources, extraction work, and derived data
- `tests/` — Python data-integrity, refresh, and scraper-resume tests
- `app/` — the Worker app (own `package.json`, everything TS)
- `SCRAPER.md` — EventPilot protocol, normalized data model, and upstream quirks
- `ROADMAP.md` — current app architecture, open work, and non-goals

## Commands

Data side (Python 3, `.venv` exists but stdlib suffices):

```bash
python3 -m unittest   # complete data, refresh, and scraper test suite
```

App side (Node LTS + pnpm via mise, run from `app/`; pnpm only — the
lockfile is `pnpm-lock.yaml`, dependency build scripts are allowlisted in
`package.json` `allowScripts`):

```bash
pnpm run program  # build a publish candidate from ../data/aaic_2026/
pnpm run check    # typecheck (svelte-check + tsc) — run before declaring done
pnpm run test     # vitest
pnpm run dev      # vite dev (Worker runs in workerd via @cloudflare/vite-plugin)
pnpm run deploy   # build + wrangler deploy (uses the dist output config)
pnpm run types    # regenerate worker-configuration.d.ts after wrangler.jsonc changes
```

## Practices

- Grug brained: KISS, YAGNI. No forced abstractions, no enterprise patterns.
  Functions do things, classes store data (Durable Object classes excepted —
  that's the platform's shape).
- TypeScript `strict` everywhere. Shared API/domain types live in
  `app/src/shared/` and are imported by both Worker and frontend — never
  duplicate a type across that boundary.
- Dependencies: minimal and mature. Justify each new one in the PR/commit.
- The Worker validates the Cloudflare Access JWT signature, issuer, and
  application audience, then uses its email claim as identity. The app has no
  auth UI.
- Secrets/cookies never committed. The EventPilot cookie comes from
  `AAIC_COOKIE` env only.

## Verification

Before considering any app change done: `pnpm run check` and `pnpm run test`
from `app/` must pass. For data changes: the unittest above must pass.
