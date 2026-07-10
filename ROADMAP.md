# Conference app — architecture and roadmap

`aaic2026.kozak.ch` is a mobile-first planning app for a small internal team at
AAIC 2026. It is live, Access-protected, and built from the committed program
dump in this repository.

## What is shipped

- Browse sessions by day or poster program, with session and presentation
  detail views.
- Scoped day/poster search and global search. Exact substring results precede
  typo-tolerant `uFuzzy` matches; abstract search is an explicit noisier option.
- Shared notes on sessions or presentations, editable and deletable by their
  author and synchronized live.
- Session/presentation RSVPs with team initials on planning views.
- Personal and team schedules assembled from RSVPs, plus the current user's
  notes.
- Venue-time (London/BST) and home-time (Zurich/CEST) display, stored as a
  per-device preference.
- CSV note export joined with program titles, and a JSON notebook snapshot used
  by the guarded refresh workflow.

## Current architecture

### One Cloudflare Worker

A single TypeScript Worker serves static assets, routes the small Hono API, and
binds the notebook Durable Object. Cloudflare's Vite plugin builds the Svelte 5
frontend and Worker together.

The Access-protected custom domain is intended to be the only production
ingress. `workers.dev` and preview URLs are disabled in `wrangler.jsonc` so they
cannot bypass Access.

The Worker validates the `Cf-Access-Jwt-Assertion` signature, issuer, and
application audience before taking identity from its email claim. Validation
uses Cloudflare's rotating JWKS through the zero-transitive-dependency `jose`
package; the team domain and audience are non-secret Worker bindings. Local
development deliberately falls back to `anonymous`.

### Static program data

`app/scripts/build-program.ts` transforms
`data/aaic_2026/{sessions,people}.json` into a content-hashed
`program.<hash>.json` asset. It:

- trims the lossless scrape to fields used by the client;
- sorts presentations by start time;
- sanitizes description HTML to bare formatting tags; and
- drops relational hints that are redundant in the nested client shape.

The current payload is about 1.9 MiB compressed. Its immutable URL makes repeat
loads cache-friendly, and all browsing and search happen client-side. There is
no D1 database: the Worker reads its static asset for the one server-side join
needed by note export.

### One team-notebook Durable Object

One named `NotebookDO` instance stores all team notes and RSVPs in its built-in
SQLite database. This deliberately avoids sharding for roughly ten users.

Clients connect through a hibernatable WebSocket. The object sends an initial
snapshot and broadcasts writes to connected clients. The client reconnects with
capped backoff after disconnection.

There is an unused notes-only REST endpoint, but no complete REST fallback in the
client. Notes and RSVP writes require a live socket; browsing the cached program
does not.

### Shared TypeScript domain

Wire and program types live in `app/src/shared/` and are imported by the Worker,
frontend, and build tooling. The frontend uses a small central Svelte store and
hash routes; it does not duplicate server-domain types or introduce a second
state framework.

## Roadmap

### Resolve the incomplete REST fallback

Choose one honest behavior:

- keep WebSocket reconnect as the only synchronization path and remove the
  unused `/api/notes` endpoint; or
- add a complete read fallback containing both notes and RSVPs and use it while
  the socket reconnects.

Do not add offline writes unless actual venue use demonstrates the need.

### Small product follow-ups

- Search kind filters for sessions, talks, and posters.
- Include RSVPs in CSV export if the team needs them centrally.
- Re-enable pnpm's `verifyDepsBeforeRun` after its upstream crash is fixed; see
  the comment in `pnpm-workspace.yaml`.

## Deliberate non-goals

- Live or automatic EventPilot scraping from the app.
- D1 or another server-side copy of immutable program data without a real query
  need.
- Full author/affiliation modeling beyond preserved formatted descriptions.
- App-managed accounts, roles, or authentication UI beyond Cloudflare Access
  and author-owned note editing.
- Durable Object sharding for a team of this size.
- Controlled-vocabulary tags, a preferences page, or framework churn.
