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

### Generalize into one multi-conference app

Turn the AAIC app into a single conference product at
`conferences.kozak.ch`, with one repository and one Worker deployment. A
conference slug is the top-level product boundary:

```text
conferences.kozak.ch/
conferences.kozak.ch/aaic-2026/
conferences.kozak.ch/ctad-2026/
conferences.kozak.ch/adpd-2027/
```

Keep the existing hash routes inside that boundary for now, for example
`/ctad-2026/#/day/2026-11-10`. The root route lists current, upcoming, and past
conferences. Keep `aaic2026.kozak.ch` as a compatibility redirect or alias.

Scope every notebook API route explicitly by conference, for example
`/api/conferences/ctad-2026/ws`. Resolve the slug through a finite conference
catalog before accessing storage; arbitrary URL slugs must not create arbitrary
Durable Object instances.

#### Stable program contract

Define a versioned, provider-independent `ConferenceProgram` schema as the only
input the app accepts. It should add conference identity and presentation
metadata to the current useful read model, including:

- a schema version distinct from the content hash;
- stable conference id, display names, dates, and IANA venue timezone;
- explicit normalized item kinds instead of tests such as
  `category === "Poster"`;
- unique conference-local item ids and valid person references; and
- a documented, sanitized representation for formatted descriptions.

Validate both structure and cross-record invariants before publication: unique
ids, references, dates, ordering, and safe HTML. Keep the nested JSON shape
optimized for whole-program client browsing and search. A normalized ingestion
contract does not require a relational runtime database.

Scrapers and provider adapters may remain source-specific, but their dependency
direction is one-way:

```text
provider scrape -> provider adapter -> validated ConferenceProgram -> app
```

The app must not import raw scraper shapes. This boundary can live in the same
repository initially; moving ingestion code elsewhere later should not change
the contract.

#### Independent, private program publishing

Store canonical conference programs in a private R2 bucket rather than Worker
static assets or Git. This keeps program data out of a potentially public app
repository and decouples data publication from Worker deployment. Do not enable
a public bucket domain or `r2.dev` access.

Use immutable, content-addressed keys plus a small catalog, conceptually:

```text
catalog.json
programs/aaic-2026/<content-hash>.json
programs/ctad-2026/<content-hash>.json
```

Publish by validating and uploading the immutable program first, then updating
the catalog pointer last. The catalog update is the promotion step and makes
rollback a pointer change. The Worker reads the private bucket through an R2
binding and serves catalog/program routes through the existing Access-protected
API. Use immutable browser caching for content-addressed programs and short or
revalidated caching for the catalog; shared public caching is unnecessary for
this small private audience.

Keep a synthetic fixture in Git for development and tests. Local development
may load an explicitly configured local program file or local R2 bucket, but
must not require committing a real conference dump.

#### Conference-scoped user data

Keep notes and RSVPs in SQLite-backed Durable Objects, with one object per
conference. Rename/migrate the existing AAIC object from the historical
`"team"` name to `"aaic-2026"`; preserve and verify its notebook data as part of
that migration. New conferences use their slug as the object name from the
start.

Do not move immutable program data or notebook data into D1 without a concrete
query need. Reconsider D1 only if server-side cross-conference search,
centralized reporting, partial program loading, or live program editing becomes
a real requirement.

#### Suggested delivery sequence

1. [x] Define the `ConferenceProgram` v1 schema and validation, with a synthetic
       fixture and the current AAIC program as the first conformance input.
2. [ ] Make conference identity, metadata, timezone handling, local-storage keys,
       titles, and export filenames generic.
3. [ ] Add path-scoped conference routing and conference-scoped API routes.
4. [ ] Split notebook storage by conference and rename/migrate AAIC's existing
       Durable Object with a verified backup.
5. [ ] Add private R2 storage and a guarded publish/promote workflow, then remove
       real conference programs from Worker assets and the working tree. Before
       making the repository public, publish from a clean history or deliberately
       rewrite the existing history; deleting the current AAIC dump in a later
       commit does not remove it from earlier commits.
6. [ ] Deploy at `conferences.kozak.ch` and retain the AAIC hostname as a
       compatibility route.
7. [ ] Build the CTAD importer against the stable contract; adapt the schema only
       for genuine cross-conference concepts, not provider quirks.

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
- A relational runtime copy of immutable program data without a real query
  need; private R2 object storage is only the publication boundary.
- Full author/affiliation modeling beyond preserved formatted descriptions.
- App-managed accounts, roles, or authentication UI beyond Cloudflare Access
  and author-owned note editing.
- Durable Object sharding for a team of this size.
- Controlled-vocabulary tags, a preferences page, or framework churn.
