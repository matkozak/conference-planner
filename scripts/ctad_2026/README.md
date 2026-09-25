# CTAD 2026 ingestion

CTAD publishes its program as PDFs and has no structured provider, so this
package is a **producer**, not an adapter: it reads the source PDFs and emits a
`ConferenceProgram` that satisfies the shared contract directly.

Sources live under the ignored `data/ctad_2026/source/`: one program PDF, one
posters PDF, and the HTML poster schedule, named `program_<date>.pdf`,
`posters_<date>.pdf`, and `poster_schedule_<date>.html`. They are saved
unchanged, exactly as acquired. The schedule comes from
`https://www.ctad-alzheimer.com/program/poster-presentation-schedule`.

## Normal workflow

Run both commands from the repository root. `mise.toml` points pnpm at `app/`
through `PNPM_CONFIG_DIR`, so no directory change is needed:

```bash
pnpm run ctad:build
pnpm run ctad:publish
```

`ctad:build`:

1. builds `app/.programs/ctad-2026.json`;
2. fails on actionable extraction findings;
3. runs the complete Python suite;
4. validates the candidate against the shared schema; and
5. runs the app type checks and tests.

Breaks, walking tours, the welcome ceremony, and social events do not need
presentations and are omitted from the review report. Empty late-breaking
sessions are listed as awaiting presentation details; check these against the
PDF after a refresh. Other empty scientific sessions fail the strict build.
Review the full list with:

```bash
python3 -m scripts.ctad_2026.build --report
```

Unmatched underline warnings include the PDF page number, coordinates in
poppler's XML space (1188 units high), and nearby text. These are candidate
marks, not a count of missing presenters. Colored dividers spanning at least
three quarters of the page width are excluded; short colored underlines remain.
Check the indicated page before deciding whether a presenter correction is
needed; unresolved talk presenters also appear as actionable report findings.

`ctad:publish` rebuilds and verifies everything, then fetches the current
production catalog, immutable CTAD program, and a fresh CTAD notebook snapshot
through Cloudflare Access. For an update, it reconciles positional ids and
checks every changed or removed item for notes and RSVPs before invoking the
generic R2 publisher. Finally, it reads production back and verifies the
catalog hash, program object, and notebook version.

The first publication has no existing CTAD identity to reconcile. Later
publications fail when an id appears to have been reused, a referenced item was
removed, or a changed item has user content that has not been acknowledged. A
reviewed non-identity change can be acknowledged explicitly:

```bash
pnpm run ctad:publish -- --allow-content-change OC12
```

This acknowledgement cannot waive possible id reuse or removal of an item with
user content. Resolve those identities or migrate the notebook data before
publishing.

`CONFERENCE_APP_URL` may override the default production origin
`https://conferences.kozak.ch`. R2 publication uses the same `R2_ACCOUNT_ID`,
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and optional `R2_BUCKET` variables
as the generic publisher.

## Source refresh

Keep exactly one `program_*.pdf` and one `posters_*.pdf` directly under
`data/ctad_2026/source/`. Before adding replacements, move the previous source
set into a dated subdirectory such as
`data/ctad_2026/source/archive/2026-07-31/`. The build does not search
subdirectories.

Capture a fresh dated copy of the poster-schedule HTML when its content changes.
Then run `pnpm run ctad:build`, perform the visual PDF spot-check, and run
`pnpm run ctad:publish`. Production itself is the immutable identity baseline;
there is no local baseline or notebook snapshot to manage.

## Low-level commands

The underlying commands remain useful for investigation:

```bash
# repository root
python3 -m scripts.ctad_2026.build
python3 -m scripts.ctad_2026.build --report

pnpm run program:check .programs/ctad-2026.json
```

Do not use the generic `program:publish` command for a routine CTAD update: it
does not perform the production identity and notebook reconciliation.

`pdftohtml` and `pdftocairo` from poppler-utils are the only
non-standard-library dependencies.

## How the extraction works

The PDFs are InDesign exports whose typography encodes the structure, so the
parsers work on positioned, font-tagged text runs from `pdftohtml -xml` rather
than on flat text. Plain `pdftotext` output loses exactly the distinctions the
document relies on.

In the program document:

- the left gutter holds times: 14-15pt for sessions, 12pt for talks. One
  session time omits the final period in `p.m`; the clock parser tolerates it;
- each gutter time pair starts a session;
- display-font headings carry the session category in their **colour** — one
  accent per kind of session — and the session's own title in black;
- bold runs open an item: `OC12`, `Presentation 2`, `BIOTECH SHOWCASE 3`;
- author names are 14pt and their affiliation markers are 8pt, so binding an
  author to their affiliation is read off the layout instead of being inferred.
  One marker is incorrectly emitted at full name size; standalone numeric runs
  in an author list are therefore always treated as affiliation markers;
- **the presenting author is underlined**, and that underline is vector art, not
  a text attribute. It is absent from the XML text layer entirely, so the
  parser also renders each page with `pdftocairo -svg` and matches the thin
  horizontal rules back onto the text runs above them. Unmatched rules produce
  a warning. The presenter is frequently not the first author — for OC9 it is
  the fifteenth.

The posters document is a flat list under theme headings, with a bold `P<n>`
label, a `Presenter:` line, an author list with the same superscript markers,
and a numbered affiliation block. It names its presenter explicitly, so it needs
no underline detection.

## Speakers and authors

Every talk and poster carries the `speaker_id` of each person who actually
presents. The program underlines every presenter, so a partially underlined
author list naturally distinguishes several speakers from the remaining
co-authors. A sole unmarked author is treated as the presenter; multiple
unmarked authors are ambiguous and reported for review.

The remaining authors are not people records. They are rendered into
`description_html` in the same shape AAIC produces, so both conferences look
alike in the app: the speaker in bold, superscript affiliation markers, and the
affiliation block after a rule.

Source author order is preserved rather than promoting the speaker to the front;
author order carries meaning, and the bold marks the speaker wherever they sit.

Only `b`, `sup` and `br` are emitted here, bare and with every source string
escaped, because publication rejects any other markup in `description_html`.

Chairs, keynote speakers and their introducers remain session speakers. Each
standalone keynote also gets one talk with the session's title and time bounds,
the keynote author's attribution and affiliation, and no introducer among its
presenters. The welcome/award ceremony remains a separate session. Session and
talk notes/RSVPs are currently separate, as for any other session with talks.
An authored standalone late-breaking symposium is represented the same way. If
the source does not underline a presenter, a guarded session override may set
`allow_missing_presenter: true` instead of guessing one.

Two source documents, one notion of a speaker: the program underlines its
presenters, the posters document names one on a `Presenter:` line, and both end
up as the same `presenting` flag on an author.

## What the PDFs do not contain

Recorded in `schedule.py`, because no source document carries them:

- the conference year, name, venue city, and timezone;
- rooms. CTAD runs one linear program in a single hall, so every session gets a
  synthetic `Main Hall` or `Poster Hall` location;
- **the poster schedule.** The posters PDF groups posters by theme only. The
  published poster-session schedule assigns those themes to days, and
  `POSTER_SESSIONS` encodes that mapping. Each theme becomes its own app session,
  titled with the theme and inheriting the published display window. Individual
  poster descriptions contain attribution only, without a repeated theme heading.
  An unrecognised theme fails the build
  rather than silently dropping posters.

Poster Session 1 runs from Monday afternoon to Tuesday evening. Its canonical
`date` is Monday and its full cross-day span is preserved in `starts_at` and
`ends_at`.

## Curated overrides

`overrides.json` holds the few corrections the layout cannot supply. Keys are
the exact collapsed source strings, so an unchanged source rebuilds
byte-identically, and a changed source shows up as an unused override in
`--report` instead of silently going stale.

- `chairs` — chair credit lines are the one place the source gives a name and an
  organisation with no typographic boundary between them, so the split is
  curated rather than guessed. An uncurated chair line is left out of the people
  store, never approximated.
- `names` — two authors are printed surname-first in the source. No casing rule
  can detect that, so the corrections are explicit.
- `orgs` — keynote bylines mix credentials and job titles into the affiliation.
- `glyph_repairs` — the posters PDF lost some glyphs from its font's ToUnicode
  map, so β, α, ε and non-breaking hyphens extract as `?`. Every extractor
  produces the same `?`; these ordered substitutions restore them. `--report`
  lists any `?` that is not ordinary sentence punctuation, which is how new
  cases are found after a source refresh.
- `sessions` — guarded presenter corrections, applied after standalone keynotes
  become presentations. Match the exact collapsed source session title, date,
  and start time, then the source presentation label (`OC12`, `Presentation2`,
  `BIOTECHSHOWCASE3`, or generated `KEYNOTE1` / `LATEBREAKINGSYMPOSIUM1`). Names
  are exact parsed author strings, before name normalization. A correction must
  provide presenters; an explicitly presenter-less source instead uses an empty
  `presenters` list plus `allow_missing_presenter: true`. For example, using
  synthetic data:

```json
{
  "match": {
    "title": "Example session",
    "date": "2026-11-16",
    "starts": "15:25:00"
  },
  "presentation": "OC12",
  "expect": {
    "authors": ["Ada Lovelace", "Grace Hopper"],
    "presenters": []
  },
  "presenters": ["Grace Hopper"],
  "reason": "PDF page 12: Grace Hopper is underlined; the mark was not matched."
}
```

Place entries in the top-level `sessions` array in `overrides.json`. `expect`
must match the current ordered author list and resolved presenter list (including
the sole-author fallback). Each selected presenter must match exactly one author.
Missing or ambiguous targets, duplicate corrections, and changed expectations
fail the build, including report mode. Keep a reason and PDF page for review.

The separate top-level `item_times` array holds guarded corrections for a source
talk time printed incorrectly. Match the globally unique source presentation
label and its exact parsed time, then record the corrected time and PDF-page
reason.

The top-level `insertions` array handles reviewed, uncoded source
entries. The parser stops extending a talk's title once authors or affiliations
begin; subsequent unrecognized bold text is retained with its page, vertical
position, nearby talk time, and preceding talk code. Unconsumed text blocks the
strict build and appears in `--report`; it does not automatically become a talk.

An insertion has the same session `match`, an `expect` object containing the
fragment's exact `after`, `page`, `top`, `starts`, and `text`, a review `reason`,
and an explicit `allow_missing_presenter: true`. It inserts that fragment as a
talk immediately after the matched source talk, using its text verbatim as the
title and its source start time. Only that inserted talk is exempted from the
missing-presenter finding. Missing or changed fragments, ambiguous sessions,
duplicate insertions, and times already occupied by extracted talks fail the
build. Additional unconsumed attribution still requires review.

The September PDF's 10:05 em dash on page 13 is handled this way: it remains a
presentation titled `—`, without inventing a source code or presenter. Rebuild
after corrections; never edit the generated candidate as a lasting fix.

Poster-specific corrections live in the `posters` override map, keyed by stable
poster id and guarded by the expected presenter. Author replacements and
numbered affiliation replacements also require exact source matches. These
handle P422's inline affiliation numbers without generalizing malformed source
formatting into parser rules. P388 explicitly allows the named presenter outside
the author list; the description credits that presenter separately. P694 allows
the visually confirmed literal question mark in its author's name.

The `[Remote]` suffix on a source poster label appears only in its location.
Its title stays unchanged and its id remains `P<n>` so existing notes and RSVPs
retain their identity.
Individual poster locations use their board label (`P233`, or `P13 [Remote]`);
poster sessions retain the `Poster Hall` location.

## Identity

CTAD omits the optional display-only `session_number` field for all sessions,
including poster sessions. Breaks, lunches, walking tours, and the welcome
ceremony default to the `Social` category.

Session ids are `S<n>` in document order; poster theme sessions use explicit stable
`PT-…` ids from `POSTER_THEME_IDS`, independent of display-window numbering. Talks keep
their source labels (`OC12`), symposium presentations become `S<n>P<m>`, biotech
showcases `BS<n>`, standalone keynotes use `KEYNOTE<n>`, standalone late-breaking
symposia use `LBS<n>`, and posters keep `P<n>`.
Manually inserted uncoded talks use `S<n>T<HHMMSS>`, scoped to their session and
source start time; they are not assigned inferred `OC` numbers.

People are keyed on normalised name plus organisation, and their ids are a hash
of that key, so they stay stable no matter what order the sources are read in.
Normalisation recases the posters document's upper-case surnames, including
hyphenated names and the `Mc` prefix — but deliberately not `Mac`, since the
sources contain both `MACDONALD` and `MACHIZAWA` and only one wants a capital.
Name-plus-organisation matching is deliberately tentative: it splits a person
who appears under two affiliations rather than merging two people who share a
name.

Because the program is preliminary, ids derived from position (`S<n>`) will
move if CTAD inserts a session. Positional ids are intentional: the source
provides no stronger identity, and a title hash would only pretend otherwise.
`ctad:publish` treats the currently published program as the identity authority
and performs the reconciliation described above.
