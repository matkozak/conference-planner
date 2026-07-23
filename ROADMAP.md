# Conference app — architecture and roadmap

The conference app is a mobile-first planning tool for a small internal team.
AAIC 2026 remains live and Access-protected at `aaic2026.kozak.ch`; the app now
has a finite multi-conference catalog and path-scoped product boundary ahead of
the `conferences.kozak.ch` deployment.

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
- Venue/home time display using each program's IANA venue timezone and the
  team's Zurich home timezone, stored as a per-device preference.
- CSV note export joined with program titles, and a JSON notebook snapshot used
  by the guarded refresh workflow.
- A root conference catalog plus conference paths such as `/aaic-2026/`. The
  catalog UI is implemented but is not exposed at a production root until
  `conferences.kozak.ch` is deployed; the historical AAIC hostname continues to
  serve AAIC directly at `/`.

## Current architecture

### One Cloudflare Worker

A single TypeScript Worker serves static assets, routes the small Hono API, and
binds the notebook Durable Object. Cloudflare's Vite plugin builds the Svelte 5
frontend and Worker together.

The Access-protected custom domain is the only production ingress. `workers.dev`
and preview URLs are disabled in `wrangler.jsonc` so they cannot bypass Access.
Currently only `aaic2026.kozak.ch` is bound. Its root is a client-side
compatibility alias for AAIC rather than an HTTP redirect; both `/` and
`/aaic-2026/` serve the same SPA and resolve to the same catalog entry.

The Worker validates the `Cf-Access-Jwt-Assertion` signature, issuer, and
application audience before taking identity from its email claim. Validation
uses Cloudflare's rotating JWKS through the zero-transitive-dependency `jose`
package; the team domain and audience are non-secret Worker bindings. Local
development deliberately falls back to `anonymous`.

### Static program data

`app/scripts/providers/eventpilot-aaic.ts` maps the lossless AAIC scrape into
the provider-independent `ConferenceProgram` contract. The adapter:

- trims the lossless scrape to fields used by the client;
- sorts presentations by start time;
- sanitizes description HTML to bare formatting tags; and
- normalizes provider conventions such as EventPilot's `Poster` category into
  explicit application item kinds.

`app/scripts/build-program.ts` invokes that adapter, validates the complete
program, writes the content-hashed `program.<hash>.json` static asset, and
generates its conference/path/hash metadata. A finite application catalog wraps
that generated metadata until the private R2 catalog replaces it. The schema
version belongs to the program contract; the content hash describes one
serialized publication.

The current payload is about 1.9 MiB compressed. Its immutable URL makes repeat
loads cache-friendly, and all browsing and search happen client-side. There is
no D1 database: the Worker reads its static asset for the one server-side join
needed by note export.

### Conference-scoped notebook Durable Objects

The `NotebookDO` class represents one conference notebook, with one named
instance per conference, named with the conference's catalog id. Each instance
stores its notes and RSVPs in built-in SQLite. AAIC's historical `"team"`
instance was copied to `"aaic-2026"` and retained as a rollback copy.

Clients connect through a hibernatable WebSocket. The object sends an initial
snapshot and broadcasts writes to connected clients. The client reconnects with
capped backoff after disconnection.

Notes and RSVP synchronization intentionally uses only the WebSocket reconnect
path. There is no partial REST fallback. Browsing the cached program does not
require a live socket.

### Shared TypeScript domain

The Zod-backed `ConferenceProgram` contract and its inferred types live in
`app/src/shared/program.ts`; notebook wire types remain in `app/src/shared/`.
Build tooling executes the structural and cross-record validation, while Worker
and frontend imports are type-only and do not bundle Zod. A generated portable
JSON Schema and invariant notes live in `schema/`.

The frontend uses a small central Svelte store and hash routes; it does not
duplicate server-domain types or introduce a second state framework.

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

The versioned, provider-independent `ConferenceProgram` schema is the only
program input the app accepts. It includes:

- a schema version distinct from the content hash;
- stable conference id, display names, dates, and IANA venue timezone;
- explicit normalized item kinds instead of tests such as
  `category === "Poster"`;
- unique conference-local item ids and valid person references; and
- a documented, sanitized representation for formatted descriptions.

The build validates structure and cross-record invariants before producing an
asset: unique ids, references, dates, ordering, and safe HTML. The nested JSON
shape remains optimized for whole-program client browsing and search. A
normalized ingestion contract does not require a relational runtime database.

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

Today, `app/scripts/build-program.ts` is AAIC-specific: it invokes the
EventPilot adapter, writes `app/public/program.<hash>.json`, and generates
`src/shared/generated/program-meta.ts`. The checked-in catalog is built from
that generated metadata, and the Worker reads the program through its `ASSETS`
binding. Phase 5 replaces this publication/storage path, not the
`ConferenceProgram` contract, provider adapters, or notebook storage.

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

The publishing entry point should accept an already constructed
`ConferenceProgram`, validate it with the shared parser, derive its
content-addressed key, upload it, and promote the catalog only after the object
is readable. Provider-specific construction stays outside that generic
publisher.

Keep a synthetic fixture in Git for development and tests. Local development
may load an explicitly configured local program file or local R2 bucket, but
must not require committing a real conference dump.

#### Conference-scoped user data

Notes and RSVPs remain in SQLite-backed Durable Objects, with one object per
conference and the conference slug as its name. AAIC has been migrated from the
historical `"team"` object to `"aaic-2026"` with its data verified; the old
object remains as a rollback copy.

Do not move immutable program data or notebook data into D1 without a concrete
query need. Reconsider D1 only if server-side cross-conference search,
centralized reporting, partial program loading, or live program editing becomes
a real requirement.

#### Suggested delivery sequence

1. [x] Define the `ConferenceProgram` v1 schema and validation, with a synthetic
       fixture and the current AAIC program as the first conformance input.
2. [x] Make conference identity, metadata, timezone handling, local-storage keys,
       titles, and export filenames generic.
3. [x] Add path-scoped conference routing and conference-scoped API routes.
4. [x] Split notebook storage by conference and rename/migrate AAIC's existing
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

#### Notes from prior design work

These are handoff context, not additional requirements. Future implementers
should revisit them when real constraints or simpler options emerge.

- Steps 2 and 3 use a small finite TypeScript catalog derived from generated
  program metadata. It is only a bridge for routing and local development; the
  R2 catalog replaces it in step 5.
- The existing Python AAIC scraper and guarded refresh pipeline are mature and
  should remain unless there is a concrete reason to replace them. A producer
  may construct `ConferenceProgram` directly or use a separate adapter; the
  adapter is optional, and the meaningful boundary is validated program JSON.
- The AAIC production notebook migration completed on 2026-07-23. Pre-copy and
  post-lock snapshots were retained locally; all 28 notes and 81 RSVPs,
  including IDs and timestamps, were verified in `"aaic-2026"` before cutover.
  The historical `"team"` object remains intact as the rollback copy.
- Start step 5 by agreeing the catalog schema, R2 binding and bucket names,
  publication CLI, and concurrent-promotion guard. Those are publication-layer
  decisions and should not leak into `ConferenceProgram`. The durable
  conclusions are private storage, immutable program objects, and promotion by
  updating the catalog last.
- CTAD currently publishes its program as a PDF. Start with the simplest
  extraction that works—possibly `pdftotext` plus layout/regex heuristics—and
  add OCR or a VLM-assisted segmenter only if the document defeats that
  approach. The validated program contract remains the handoff either way.
- Domain, Access, and production-route changes in step 6 are coordinated
  operations and should be checked against the current Cloudflare configuration
  at implementation time.

### WebSocket-only synchronization

The unused notes-only REST endpoint has been removed. WebSocket reconnect is the
one synchronization path for notes and RSVPs. Do not add offline writes unless
actual venue use demonstrates the need.

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
