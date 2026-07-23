/** EventPilot/AAIC adapter: raw scraper records in, validated app contract out. */
import type {
  ConferenceProgram,
  Person,
  Presentation,
  Session,
} from "../../src/shared/program.ts";
import {
  CONFERENCE_PROGRAM_SCHEMA_VERSION,
  parseConferenceProgram,
} from "../../src/shared/program.ts";

export interface RawEventPilotItem {
  id: string;
  title: string;
  date?: string;
  starts_at?: string;
  ends_at?: string;
  location?: string;
  category?: string;
  session_number?: string;
  speaker_ids?: string[];
  description_text?: string;
  description_html?: string;
  presentations?: RawEventPilotItem[];
}

export interface RawEventPilotPerson {
  full_name?: string;
  first_name?: string;
  last_name?: string;
  organization?: string;
}

/** Drop undefined/empty fields so the payload stays small. */
function prune<T extends object>(obj: T): T {
  return Object.fromEntries(
    Object.entries(obj).filter(
      ([, value]) => value !== undefined && value !== "" && value !== null,
    ),
  ) as T;
}

/**
 * The current dump only uses a subset of these tags, but the contract permits
 * the same conservative formatting allowlist for every provider.
 */
const ALLOWED_TAGS = new Set([
  "b",
  "br",
  "sup",
  "sub",
  "i",
  "em",
  "strong",
  "p",
]);

export function sanitizeHtml(html: string): string {
  return html
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(
      /<\s*(\/?)\s*([a-zA-Z0-9]+)[^>]*>/g,
      (_match, slash: string, tag: string) =>
        ALLOWED_TAGS.has(tag.toLowerCase())
          ? `<${slash}${tag.toLowerCase()}>`
          : "",
    );
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

/** Prefer sanitized provider HTML; fall back to escaped plain text. */
export function descriptionOf(raw: RawEventPilotItem): string | undefined {
  const html = raw.description_html?.trim();
  if (html) return sanitizeHtml(html);
  const text = raw.description_text?.trim();
  if (text) return escapeHtml(text).replace(/\n/g, "<br>");
  return undefined;
}

type PresentationFields = Omit<Presentation, "kind">;

function presentationFields(raw: RawEventPilotItem): PresentationFields {
  return prune({
    id: raw.id,
    title: raw.title,
    starts_at: raw.starts_at,
    ends_at: raw.ends_at,
    location: normalizeLocation(raw.location),
    speaker_ids: raw.speaker_ids?.length ? raw.speaker_ids : undefined,
    description_html: descriptionOf(raw),
  });
}

/** Normalize EventPilot display conventions before they reach the app. */
function normalizeLocation(location?: string): string | undefined {
  return location?.replace(/^Board no\.\s*/, "");
}

function normalizeSessionTitle(raw: RawEventPilotItem): string {
  let title = raw.title;
  const categoryPrefix = raw.category && `${raw.category} - `;
  if (categoryPrefix && title.startsWith(categoryPrefix)) {
    title = title.slice(categoryPrefix.length);
  }
  if (raw.category === "Poster") {
    title = title.replace(/^\[[^\]]*\]\s*/, "");
  }
  return title;
}

export function trimPresentation(
  raw: RawEventPilotItem,
  kind: Presentation["kind"] = "talk",
): Presentation {
  return { kind, ...presentationFields(raw) };
}

export function trimSession(raw: RawEventPilotItem): Session {
  if (!raw.date) throw new Error(`session ${raw.id} has no date`);
  const poster = raw.category === "Poster";
  const presentationKind = poster ? "poster" : "talk";
  return {
    kind: poster ? "poster-session" : "session",
    ...presentationFields(raw),
    title: normalizeSessionTitle(raw),
    ...prune({ category: raw.category, session_number: raw.session_number }),
    date: raw.date,
    // EventPilot's child order is frequently rotated; missing times sort last.
    presentations: (raw.presentations ?? [])
      .map((item) => trimPresentation(item, presentationKind))
      .sort(comparePresentations),
  };
}

export function trimPerson(raw: RawEventPilotPerson): Person {
  const name =
    raw.full_name ||
    [raw.first_name, raw.last_name].filter(Boolean).join(" ") ||
    "Unknown";
  return prune({ name, org: raw.organization || undefined });
}

export function adaptAaicProgram(
  rawSessions: RawEventPilotItem[],
  rawPeople: Record<string, RawEventPilotPerson>,
): ConferenceProgram {
  const sessions = rawSessions.map(trimSession).sort(compareSessions);
  const days = [...new Set(sessions.map((session) => session.date))].sort();
  const people = Object.fromEntries(
    Object.entries(rawPeople).map(([id, person]) => [id, trimPerson(person)]),
  );

  return parseConferenceProgram({
    schema_version: CONFERENCE_PROGRAM_SCHEMA_VERSION,
    conference: {
      id: "aaic-2026",
      name: "Alzheimer's Association International Conference 2026",
      short_name: "AAIC 2026",
      starts_on: days[0],
      ends_on: days.at(-1),
      timezone: "Europe/London",
    },
    days,
    sessions,
    people,
  });
}

function comparePresentations(a: Presentation, b: Presentation): number {
  return (a.starts_at ?? "\uffff").localeCompare(b.starts_at ?? "\uffff");
}

function compareSessions(a: Session, b: Session): number {
  return (
    a.date.localeCompare(b.date) ||
    (a.starts_at ?? "\uffff").localeCompare(b.starts_at ?? "\uffff") ||
    a.title.localeCompare(b.title) ||
    a.id.localeCompare(b.id)
  );
}
