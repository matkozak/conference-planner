# ConferenceProgram contract

`conference-program-v1.schema.json` is the portable structural contract for
programs accepted by the conference application. It is generated from
`app/src/shared/program.ts`; edit the Zod schema rather than the JSON file.

Publication validation also enforces invariants that JSON Schema cannot express:

- item ids are unique across sessions and presentations;
- every `speaker_ids` entry names a person in `people` and contains no duplicate;
- `days` is sorted, unique, within the conference range, and exactly matches the
  dates represented by sessions;
- sessions and presentations use the documented canonical ordering;
- timestamps use their containing session's date and do not run backwards;
- `talk` items occur in `session` parents and `poster` items in
  `poster-session` parents; and
- the conference timezone is a recognized IANA name.

`description_html`, when present, is already sanitized display content. Producers
must escape plain text and may emit only text plus bare `b`, `br`, `sup`, `sub`,
`i`, `em`, `strong`, and `p` tags. Consumers may render this field as HTML; no
other program string should be interpreted as markup.
