# App Roadmap — aaic2026.kozak.ch

A conference planning app for ~10 internal users, better than the official one.
Ship date: today (2026-07-08). Conference: 2026-07-10 → 2026-07-16.

## Architecture

All decisions confirmed by Mateusz on 2026-07-08. The program asset keeps the
nested `presentations`-on-parent shape and drops the relational hints
(`parent_id`, `subsession_ids`) — the client builds a `Map<id, item>` at load.

### Platform: one Cloudflare Worker, full TypeScript

- Single Worker serves static assets + a small API + hosts the Durable Object.
- No Rust/WASM, no separate backend — YAGNI for 10 users.
- Hono for Worker routing (tiny, typed, mature).
- Access control: **Cloudflare Access** in front of `aaic2026.kozak.ch` with an
  email allowlist. The Worker trusts the `Cf-Access-Authenticated-User-Email`
  header — safe because the Access-protected custom domain is the only ingress
  (workers.dev and preview URLs are disabled; Access strips inbound `Cf-Access-*`
  headers). No JWT validation in the Worker; revisit if another ingress ever
  appears. That email _is_ the user identity. Zero auth UI.

### Program data: static JSON asset, not D1

The full trimmed program (all sessions, presentations, descriptions, people
names) is ~1.7 MB gzipped. So:

- A build script (`app/scripts/build-program.ts`) transforms
  `data/aaic_2026/sessions.json` + `people.json` into a versioned static asset
  (`program.<hash>.json`) served with immutable cache headers. It sorts
  presentations by start time (EventPilot's order is unreliable) and ships
  descriptions as sanitized HTML (bare b/br/sup/sub/i/em/strong/p only).
- The client fetches it once, caches it; all browsing/search is client-side
  and instant — and works on terrible venue WiFi.
- **No D1 at all** (original plan was SQLite→D1; dropped because the Worker can
  read its own static asset for the one server-side need, the notes export).
  D1 remains a cheap escape hatch if a real server-side query need appears.

### User data: one Durable Object = "the team notebook"

- A single named DO instance holds all user-generated data (notes, tags,
  RSVPs) in its built-in SQLite storage. 10 users → one object, no sharding.
- Clients connect via WebSocket (hibernation API); writes broadcast to all
  connected clients, so everyone sees notes/RSVPs live.
- Fallback path: plain `fetch` endpoints on the DO for initial load and for
  clients whose socket dropped.
- Alternative considered: D1 tables + polling. Simpler but no liveness, and
  the DO is the textbook fit here.

### Frontend: Svelte 5 + Vite + TypeScript

- Elm-_style_, not Elm: one central store module, unidirectional data flow,
  messages-as-functions. No second language, shared types with the Worker.
- Mobile-first layout; the phone in the conference hallway is the primary
  device.
- Fuzzy search: `uFuzzy` (tiny, excellent) over an in-memory index of titles +
  speakers + locations.

### Repo shape

```
app/
  package.json          # single package, no workspaces
  wrangler.jsonc
  scripts/build-program.ts
  src/
    worker/             # Hono app + NotebookDO
    shared/             # types shared by worker & client (Note, Rsvp, Program…)
    app/                # Svelte frontend
  public/               # built program asset + static files
```

## Milestones

Status 2026-07-08: M1–M3 shipped and live at aaic2026.kozak.ch, correctness
review pass applied (notes reactivity, CSV title join + BOM, back-nav,
reconnect backoff). Two polish rounds shipped on top: a Posters tab (posters
out of the daily program, board-number search), honest search-result kinds
with talk-level deep links (`#/s/<session>/<talk>`), sorted talks, HTML
descriptions, unique-previous back stack with scroll restoration, persistent
search queries, two-tap note deletion, and a day-view search bar. The Zero
Trust org label was renamed to "kozak.ch". From M4, RSVPs and the "My stuff"
view are built; tags were dropped and offline polish deferred (the immutable
program asset already covers most of it).

### M1 — Walking skeleton (get the pipeline proven early)

- `app/` scaffold: Vite + Svelte 5 + Hono + wrangler, strict TS, vitest.
- `build-program.ts` producing the trimmed program asset.
- Worker serving the SPA + program asset.
- Deploy to `aaic2026.kozak.ch` (DNS + Worker route + Cloudflare Access
  policy). Allowlist currently: mateusz.kozak@acimmune.com; add the rest of
  the team before the conference.

### M2 — Browse & find

- Day navigation, defaulting to _today_ in the user's local timezone; sticky
  day selection.
- Session list → session detail with presentations, times, rooms, speakers.
- Fuzzy finder (fast, keyboard- and thumb-friendly).

### M3 — Notes (the point of the whole thing)

- NotebookDO with SQLite schema: `notes(id, item_id, author, body,
created_at, updated_at)`.
- Notes attach to sessions _or_ presentations; visible to everyone; editable
  by their author.
- Live sync via WebSocket broadcast.
- Export endpoint for the central authority: all notes as CSV/XLSX-friendly
  download, joined with session/presentation titles.

### M4 — Bonus (only if the day allows)

- ✅ "I'll be there" RSVP per session/talk: toggle + initials chips on the
  detail view, aggregated team initials (session ∪ its talks) on day cards.
  `rsvps(item_id, author)` table in the NotebookDO, idempotent `rsvp:set`
  toggle message, included in the WS snapshot.
- ✅ "My stuff" view (`#/me`, "Me" tab): my RSVP schedule grouped by day and
  my notes, with jump-to-item links.
- ✂️ Controlled-vocabulary tags — dropped (2026-07-08).
- ✂️ Offline polish — deferred; the immutable-cached program asset covers
  the browsing case already.

## Deliberately not doing

- Live re-scraping from the app (scraper stays a manual, periodic process).
- Author/affiliation parsing beyond the formatted `description_html` block.
- Accounts, roles, permissions beyond Access + author-owns-their-notes.
- Access JWT validation in the Worker (single Access-only ingress instead).
- Any framework churn after M1.
