/**
 * Builds the immutable program asset from the scraped dump.
 *
 * Reads  ../data/aaic_2026/{sessions,people}.json
 * Writes public/program.<hash>.json          (the trimmed payload)
 *        public/_headers                     (immutable cache headers)
 *        src/shared/generated/program-meta.ts (typed path constant)
 *
 * Run from app/: `pnpm run program` (plain Node, type-stripped).
 */
import { createHash } from "node:crypto";
import {
  mkdirSync,
  readdirSync,
  readFileSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";

import type {
  Person,
  Presentation,
  Program,
  Session,
} from "../src/shared/types.ts";

const APP_ROOT = join(import.meta.dirname, "..");
const DATA_DIR = join(APP_ROOT, "..", "data", "aaic_2026");

// --- Raw dump shapes (only the fields we read) ---

interface RawItem {
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
  presentations?: RawItem[];
}

interface RawPerson {
  full_name?: string;
  first_name?: string;
  last_name?: string;
  organization?: string;
}

// --- Pure transform (exported for tests) ---

/** Drop undefined/empty fields so the payload stays small. */
function prune<T extends object>(obj: T): T {
  return Object.fromEntries(
    Object.entries(obj).filter(
      ([, v]) => v !== undefined && v !== "" && v !== null,
    ),
  ) as T;
}

/**
 * The scraped description_html only ever contains <sup>/<b>/<br>/<p> (verified
 * against the full dump), but sanitize defensively anyway: keep an allowlist
 * of bare formatting tags, strip all attributes and everything else.
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
      (_m, slash: string, tag: string) =>
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

/** Prefer the (sanitized) HTML description; fall back to escaped plain text. */
export function descriptionOf(raw: RawItem): string | undefined {
  const html = raw.description_html?.trim();
  if (html) return sanitizeHtml(html);
  const text = raw.description_text?.trim();
  if (text) return escapeHtml(text).replace(/\n/g, "<br>");
  return undefined;
}

export function trimPresentation(raw: RawItem): Presentation {
  return prune({
    id: raw.id,
    title: raw.title,
    starts_at: raw.starts_at,
    ends_at: raw.ends_at,
    location: raw.location,
    speaker_ids: raw.speaker_ids?.length ? raw.speaker_ids : undefined,
    description: descriptionOf(raw),
  });
}

export function trimSession(raw: RawItem): Session {
  if (!raw.date) throw new Error(`session ${raw.id} has no date`);
  // EventPilot's subsession order is unreliable (frequently rotated); sort by
  // start time, items without one last. Array.sort is stable, so ties keep
  // the scraped order.
  const NO_TIME = "￿";
  return {
    ...trimPresentation(raw),
    ...prune({ category: raw.category, session_number: raw.session_number }),
    date: raw.date,
    presentations: (raw.presentations ?? [])
      .map(trimPresentation)
      .sort((a, b) =>
        (a.starts_at ?? NO_TIME).localeCompare(b.starts_at ?? NO_TIME),
      ),
  };
}

export function trimPerson(raw: RawPerson): Person {
  const name =
    raw.full_name ||
    [raw.first_name, raw.last_name].filter(Boolean).join(" ") ||
    "Unknown";
  return prune({ name, org: raw.organization || undefined });
}

export function buildProgram(
  rawSessions: RawItem[],
  rawPeople: Record<string, RawPerson>,
): Program {
  const sessions = rawSessions.map(trimSession);
  const days = [...new Set(sessions.map((s) => s.date))].sort();
  const people = Object.fromEntries(
    Object.entries(rawPeople).map(([id, p]) => [id, trimPerson(p)]),
  );
  const versionless = JSON.stringify({ days, sessions, people });
  const version = createHash("sha256")
    .update(versionless)
    .digest("hex")
    .slice(0, 8);
  return { version, days, sessions, people };
}

// --- Build ---

function main(): void {
  const rawSessions: RawItem[] = JSON.parse(
    readFileSync(join(DATA_DIR, "sessions.json"), "utf8"),
  );
  const rawPeople: Record<string, RawPerson> = JSON.parse(
    readFileSync(join(DATA_DIR, "people.json"), "utf8"),
  );

  const program = buildProgram(rawSessions, rawPeople);
  const assetName = `program.${program.version}.json`;

  const publicDir = join(APP_ROOT, "public");
  mkdirSync(publicDir, { recursive: true });
  for (const stale of readdirSync(publicDir).filter(
    (f) => f.startsWith("program.") && f.endsWith(".json") && f !== assetName,
  )) {
    unlinkSync(join(publicDir, stale));
  }
  writeFileSync(join(publicDir, assetName), JSON.stringify(program));

  // Content-hashed names never change content: cache forever.
  writeFileSync(
    join(publicDir, "_headers"),
    [
      `/${assetName}`,
      "  Cache-Control: public, max-age=31536000, immutable",
      "/assets/*",
      "  Cache-Control: public, max-age=31536000, immutable",
      "",
    ].join("\n"),
  );

  const genDir = join(APP_ROOT, "src", "shared", "generated");
  mkdirSync(genDir, { recursive: true });
  writeFileSync(
    join(genDir, "program-meta.ts"),
    `// Generated by scripts/build-program.ts — do not edit.\nexport const PROGRAM_PATH = '/${assetName}';\n`,
  );

  const talks = program.sessions.reduce(
    (n, s) => n + s.presentations.length,
    0,
  );
  console.log(
    `wrote ${assetName}: ${program.days.length} days, ${program.sessions.length} sessions, ` +
      `${talks} talks, ${Object.keys(program.people).length} people`,
  );
}

if (process.argv[1] === import.meta.filename) main();
