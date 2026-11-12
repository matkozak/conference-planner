# ConferenceProgram producer contract

`conference-program-v1.schema.json` is the portable structural contract for
programs accepted by the conference application. It is generated from
`app/src/shared/program.ts`; edit the Zod schema rather than the JSON file.

The
[`conference-program-producers`](https://github.com/matkozak/conference-program-producers)
repository emits one complete JSON document. Raw provider shapes,
source documents, parsing artifacts, credentials, and producer-specific
configuration do not cross this boundary. The synthetic
`app/fixtures/synthetic-program.json` demonstrates the full document shape.

## Producer responsibilities

A producer must:

- choose a stable lowercase conference ID;
- preserve every session and presentation ID across rebuilds for as long as
  the item represents the same real-world thing;
- assign a new ID rather than reuse an old one for different content;
- emit globally unique item IDs within the conference;
- emit complete people records for every `speaker_ids` reference;
- sort days, sessions, and presentations canonically; and
- provide already-sanitized `description_html` when using rich text.

Publication validation enforces invariants JSON Schema cannot express:

- item IDs are unique across sessions and presentations;
- every `speaker_ids` entry resolves and contains no duplicate;
- `days` is sorted, unique, within the conference range, and exactly matches
  the dates represented by sessions;
- sessions and presentations use the documented canonical ordering;
- session and presentation timestamps are real and remain within their allowed
  conference/session spans;
- `talk` items occur in `session` parents and `poster` items occur in
  `poster-session` parents; and
- the conference timezone is a recognized IANA name.

`description_html` may contain text plus bare `b`, `br`, `sup`, `sub`, `i`,
`em`, `strong`, and `p` tags only. Producers must escape all source text before
placing it in HTML. No other program string is interpreted as markup.

## Update safety

The application treats the currently published program as the identity
authority. Before an update, the publication tools compare the candidate with
that exact baseline and a fresh conference-scoped notebook export.

Publication blocks:

- likely reuse of an existing item ID for a different item;
- removal of an item that has notes or RSVPs; and
- modification of an item with notes or RSVPs unless the operator explicitly
  acknowledges that non-identity content change.

Possible ID reuse is never waivable. An acknowledgment does not migrate or
delete user content; it only records an operator's decision that the stable
identity still refers to the same item.

Run `pnpm run program:check <program.json>` for offline contract validation and
`pnpm run program:review <program.json>` for the production comparison.
