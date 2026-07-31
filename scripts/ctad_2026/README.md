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

Known empty source sessions are summarized without failing the build. Review
their full list with:

```bash
python3 -m scripts.ctad_2026.build --report
```

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

Chairs, keynote speakers and their introducers are session speakers.

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
  `POSTER_SESSIONS` encodes that mapping. An unrecognised theme fails the build
  rather than silently dropping posters.

Poster Session 1 runs from Monday afternoon to Tuesday evening. A session in the
schema belongs to one date, so it is dated Monday with no end time, and the true
span is stated in its description.

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

## Identity

Session ids are `S<n>` in document order; poster sessions are `PS<n>`. Talks keep
their source labels (`OC12`), symposium presentations become `S<n>P<m>`, biotech
showcases `BS<n>`, and posters keep `P<n>`.

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
