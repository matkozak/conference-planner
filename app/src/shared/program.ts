import { z } from "zod";

export const CONFERENCE_PROGRAM_SCHEMA_VERSION = 1 as const;
export const CONFERENCE_PROGRAM_SCHEMA_ID =
  "https://conferences.kozak.ch/schemas/conference-program-v1.schema.json";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const ISO_TIMESTAMP =
  /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;

const nonEmptyString = z.string().min(1);
const conferenceId = z
  .string()
  .regex(
    /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
    "expected a lowercase URL-safe conference id",
  );
const itemId = nonEmptyString.meta({
  description: "A unique conference-local item identifier.",
});
const isoDate = z.string().regex(ISO_DATE, "expected YYYY-MM-DD");
const isoTimestamp = z
  .string()
  .regex(ISO_TIMESTAMP, "expected an ISO 8601 timestamp with an offset");

export const personSchema = z.strictObject({
  name: nonEmptyString,
  org: nonEmptyString.optional(),
});

const scheduledItemShape = {
  id: itemId,
  title: nonEmptyString,
  starts_at: isoTimestamp.optional(),
  ends_at: isoTimestamp.optional(),
  location: nonEmptyString.optional(),
  speaker_ids: z.array(nonEmptyString).min(1).optional(),
  description_html: nonEmptyString
    .meta({
      description:
        "Sanitized HTML containing text and bare b, br, sup, sub, i, em, strong, and p tags only.",
    })
    .optional(),
};

export const presentationSchema = z.strictObject({
  kind: z.enum(["talk", "poster"]),
  ...scheduledItemShape,
});

export const sessionSchema = z.strictObject({
  kind: z.enum(["session", "poster-session"]),
  ...scheduledItemShape,
  date: isoDate,
  /** Optional provider-supplied display label; application logic must use kind. */
  category: nonEmptyString.optional(),
  session_number: nonEmptyString.optional(),
  presentations: z.array(presentationSchema),
});

export const conferenceProgramSchema = z
  .strictObject({
    schema_version: z.literal(CONFERENCE_PROGRAM_SCHEMA_VERSION),
    conference: z.strictObject({
      /** Stable id and current URL slug. Catalog aliases may be added later. */
      id: conferenceId,
      name: nonEmptyString,
      short_name: nonEmptyString,
      starts_on: isoDate,
      ends_on: isoDate,
      /** IANA timezone name, validated as a publication invariant. */
      timezone: nonEmptyString,
    }),
    /** Sorted unique conference dates represented by sessions. */
    days: z.array(isoDate).min(1),
    sessions: z.array(sessionSchema).min(1),
    people: z.record(nonEmptyString, personSchema),
  })
  .meta({
    id: CONFERENCE_PROGRAM_SCHEMA_ID,
    title: "ConferenceProgram v1",
    description:
      "Provider-independent, whole-program read model consumed by the conference application.",
  });

export type ConferenceProgram = z.infer<typeof conferenceProgramSchema>;
export type Conference = ConferenceProgram["conference"];
export type Person = z.infer<typeof personSchema>;
export type Presentation = z.infer<typeof presentationSchema>;
export type Session = z.infer<typeof sessionSchema>;

export interface ProgramValidationIssue {
  path: string;
  message: string;
}

export class ProgramValidationError extends Error {
  readonly issues: ProgramValidationIssue[];

  constructor(issues: ProgramValidationIssue[]) {
    super(
      `Invalid ConferenceProgram:\n${issues
        .map(({ path, message }) => `- ${path}: ${message}`)
        .join("\n")}`,
    );
    this.name = "ProgramValidationError";
    this.issues = issues;
  }
}

/** Parse the structural schema, then enforce cross-record publication rules. */
export function parseConferenceProgram(value: unknown): ConferenceProgram {
  const parsed = conferenceProgramSchema.safeParse(value);
  if (!parsed.success) {
    throw new ProgramValidationError(
      parsed.error.issues.map((issue) => ({
        path: pathOf(issue.path),
        message: issue.message,
      })),
    );
  }

  const issues = conferenceProgramInvariantIssues(parsed.data);
  if (issues.length > 0) throw new ProgramValidationError(issues);
  return parsed.data;
}

/** Portable structural schema; cross-record invariants remain documented code. */
export function conferenceProgramJsonSchema(): Record<string, unknown> {
  const generated = z.toJSONSchema(conferenceProgramSchema, {
    target: "draft-2020-12",
    reused: "ref",
  });
  return { ...generated, $id: CONFERENCE_PROGRAM_SCHEMA_ID };
}

function pathOf(path: PropertyKey[]): string {
  if (path.length === 0) return "$";
  return path.reduce<string>(
    (result, part) =>
      typeof part === "number"
        ? `${result}[${part}]`
        : `${result}.${String(part)}`,
    "$",
  );
}

function conferenceProgramInvariantIssues(
  program: ConferenceProgram,
): ProgramValidationIssue[] {
  const issues: ProgramValidationIssue[] = [];
  const issue = (path: string, message: string) =>
    issues.push({ path, message });
  const { conference } = program;

  if (!isRealIsoDate(conference.starts_on)) {
    issue("$.conference.starts_on", "must be a real calendar date");
  }
  if (!isRealIsoDate(conference.ends_on)) {
    issue("$.conference.ends_on", "must be a real calendar date");
  }
  if (conference.starts_on > conference.ends_on) {
    issue("$.conference", "starts_on must not be after ends_on");
  }
  if (!isIanaTimezone(conference.timezone)) {
    issue("$.conference.timezone", "must be a recognized IANA timezone");
  }

  const sessionDates = new Set<string>();
  for (const [index, day] of program.days.entries()) {
    if (!isRealIsoDate(day))
      issue(`$.days[${index}]`, "must be a real calendar date");
    if (index > 0 && day <= (program.days[index - 1] ?? "")) {
      issue(`$.days[${index}]`, "days must be unique and strictly sorted");
    }
    if (day < conference.starts_on || day > conference.ends_on) {
      issue(`$.days[${index}]`, "falls outside the conference date range");
    }
  }

  const itemIds = new Map<string, string>();
  for (const [sessionIndex, session] of program.sessions.entries()) {
    const sessionPath = `$.sessions[${sessionIndex}]`;
    sessionDates.add(session.date);
    recordItemId(itemIds, session.id, `${sessionPath}.id`, issue);
    validateScheduledItem(session, sessionPath, program, issue);

    if (!isRealIsoDate(session.date)) {
      issue(`${sessionPath}.date`, "must be a real calendar date");
    }
    if (!program.days.includes(session.date)) {
      issue(`${sessionPath}.date`, "must be present in program days");
    }
    validateTimestampDate(
      session.starts_at,
      session.date,
      `${sessionPath}.starts_at`,
      issue,
    );
    validateTimestampDate(
      session.ends_at,
      session.date,
      `${sessionPath}.ends_at`,
      issue,
    );

    const expectedPresentationKind =
      session.kind === "poster-session" ? "poster" : "talk";
    let previousStart = "";
    for (const [
      presentationIndex,
      presentation,
    ] of session.presentations.entries()) {
      const presentationPath = `${sessionPath}.presentations[${presentationIndex}]`;
      recordItemId(itemIds, presentation.id, `${presentationPath}.id`, issue);
      validateScheduledItem(presentation, presentationPath, program, issue);
      validateTimestampDate(
        presentation.starts_at,
        session.date,
        `${presentationPath}.starts_at`,
        issue,
      );
      validateTimestampDate(
        presentation.ends_at,
        session.date,
        `${presentationPath}.ends_at`,
        issue,
      );
      if (presentation.kind !== expectedPresentationKind) {
        issue(
          `${presentationPath}.kind`,
          `must be ${expectedPresentationKind} inside a ${session.kind}`,
        );
      }

      const start = presentation.starts_at ?? "\uffff";
      if (start < previousStart) {
        issue(
          `${presentationPath}.starts_at`,
          "presentations must be sorted by start time, with missing times last",
        );
      }
      previousStart = start;
    }

    if (sessionIndex > 0) {
      const previous = program.sessions[sessionIndex - 1];
      if (previous && compareSessions(previous, session) > 0) {
        issue(
          sessionPath,
          "sessions must be sorted by date, start time, title, and id",
        );
      }
    }
  }

  const representedDates = [...sessionDates].sort();
  if (
    representedDates.length !== program.days.length ||
    representedDates.some((day, index) => day !== program.days[index])
  ) {
    issue("$.days", "must exactly match the sorted unique session dates");
  }

  return issues;
}

type ScheduledItem = Session | Presentation;

function validateScheduledItem(
  item: ScheduledItem,
  path: string,
  program: ConferenceProgram,
  issue: (path: string, message: string) => void,
): void {
  if (item.starts_at && !isRealTimestamp(item.starts_at)) {
    issue(`${path}.starts_at`, "must be a real ISO 8601 timestamp");
  }
  if (item.ends_at && !isRealTimestamp(item.ends_at)) {
    issue(`${path}.ends_at`, "must be a real ISO 8601 timestamp");
  }
  if (
    item.starts_at &&
    item.ends_at &&
    Date.parse(item.starts_at) > Date.parse(item.ends_at)
  ) {
    issue(path, "starts_at must not be after ends_at");
  }

  const seenSpeakers = new Set<string>();
  for (const [index, personId] of (item.speaker_ids ?? []).entries()) {
    if (!Object.hasOwn(program.people, personId)) {
      issue(
        `${path}.speaker_ids[${index}]`,
        `unknown person id ${JSON.stringify(personId)}`,
      );
    }
    if (seenSpeakers.has(personId)) {
      issue(`${path}.speaker_ids[${index}]`, "speaker ids must be unique");
    }
    seenSpeakers.add(personId);
  }

  if (
    item.description_html &&
    !isSanitizedDescriptionHtml(item.description_html)
  ) {
    issue(
      `${path}.description_html`,
      "must contain text and allowlisted bare formatting tags only",
    );
  }
}

function recordItemId(
  ids: Map<string, string>,
  id: string,
  path: string,
  issue: (path: string, message: string) => void,
): void {
  const previous = ids.get(id);
  if (previous) issue(path, `duplicates item id already used at ${previous}`);
  else ids.set(id, path);
}

function validateTimestampDate(
  timestamp: string | undefined,
  expectedDate: string,
  path: string,
  issue: (path: string, message: string) => void,
): void {
  if (timestamp && timestamp.slice(0, 10) !== expectedDate) {
    issue(path, `must use the containing session date ${expectedDate}`);
  }
}

function compareSessions(a: Session, b: Session): number {
  return (
    a.date.localeCompare(b.date) ||
    (a.starts_at ?? "\uffff").localeCompare(b.starts_at ?? "\uffff") ||
    a.title.localeCompare(b.title) ||
    a.id.localeCompare(b.id)
  );
}

function isRealIsoDate(value: string): boolean {
  const date = new Date(`${value}T00:00:00Z`);
  return (
    !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value
  );
}

function isRealTimestamp(value: string): boolean {
  return ISO_TIMESTAMP.test(value) && !Number.isNaN(Date.parse(value));
}

function isIanaTimezone(value: string): boolean {
  try {
    new Intl.DateTimeFormat("en", { timeZone: value }).format();
    return true;
  } catch (error) {
    if (error instanceof RangeError) return false;
    throw error;
  }
}

const ALLOWED_DESCRIPTION_TAG = /^<\/?(?:b|br|sup|sub|i|em|strong|p)>$/;

function isSanitizedDescriptionHtml(value: string): boolean {
  const tags = value.match(/<[^>]*>/g) ?? [];
  return tags.every((tag) => ALLOWED_DESCRIPTION_TAG.test(tag));
}
