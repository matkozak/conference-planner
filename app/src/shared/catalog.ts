import type { Conference } from "./program";

export const CONFERENCE_CATALOG_SCHEMA_VERSION = 1 as const;
export const CATALOG_KEY = "catalog.json";

const CONFERENCE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const CONTENT_HASH = /^[a-f0-9]{64}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

export interface ConferenceCatalogEntry extends Conference {
  program_hash: string;
}

export interface ConferenceCatalog {
  schema_version: typeof CONFERENCE_CATALOG_SCHEMA_VERSION;
  conferences: ConferenceCatalogEntry[];
}

/** R2 key for one immutable, content-addressed program publication. */
export function programKey(conferenceId: string, hash: string): string {
  return `programs/${conferenceId}/${hash}.json`;
}

/** Authenticated browser route for an immutable program publication. */
export function programPath(conference: ConferenceCatalogEntry): string {
  return `/api/${programKey(conference.id, conference.program_hash)}`;
}

/** Parse the small publication catalog without pulling Zod into the app bundle. */
export function parseConferenceCatalog(value: unknown): ConferenceCatalog {
  if (!isRecord(value)) throw new Error("catalog must be an object");
  if (value.schema_version !== CONFERENCE_CATALOG_SCHEMA_VERSION) {
    throw new Error(
      `unsupported catalog schema version: ${String(value.schema_version)}`,
    );
  }
  if (!Array.isArray(value.conferences)) {
    throw new Error("catalog conferences must be an array");
  }

  const ids = new Set<string>();
  const conferences = value.conferences.map((entry, index) => {
    const path = `catalog.conferences[${index}]`;
    if (!isRecord(entry)) throw new Error(`${path} must be an object`);
    const conference = {
      id: requiredString(entry, "id", path, CONFERENCE_ID),
      name: requiredString(entry, "name", path),
      short_name: requiredString(entry, "short_name", path),
      starts_on: requiredString(entry, "starts_on", path, ISO_DATE),
      ends_on: requiredString(entry, "ends_on", path, ISO_DATE),
      timezone: requiredString(entry, "timezone", path),
      program_hash: requiredString(entry, "program_hash", path, CONTENT_HASH),
    };
    if (ids.has(conference.id)) {
      throw new Error(`${path}.id duplicates ${conference.id}`);
    }
    if (conference.starts_on > conference.ends_on) {
      throw new Error(`${path} starts after it ends`);
    }
    ids.add(conference.id);
    return conference;
  });

  return {
    schema_version: CONFERENCE_CATALOG_SCHEMA_VERSION,
    conferences,
  };
}

export function conferenceById(
  catalog: ConferenceCatalog,
  id: string,
): ConferenceCatalogEntry | undefined {
  return catalog.conferences.find((conference) => conference.id === id);
}

/**
 * Resolve a browser pathname to a finite catalog entry.
 *
 * null means the catalog root; undefined means an invalid/unknown path.
 */
export function conferenceForLocation(
  catalog: ConferenceCatalog,
  pathname: string,
  hostname: string,
): ConferenceCatalogEntry | null | undefined {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) {
    const legacyId = LEGACY_HOST_CONFERENCES[hostname];
    return legacyId ? conferenceById(catalog, legacyId) : null;
  }
  if (parts.length !== 1) return undefined;
  return conferenceById(catalog, parts[0] ?? "");
}

export type ConferenceStatus = "current" | "upcoming" | "past";

export function conferenceStatus(
  conference: ConferenceCatalogEntry,
  today: string,
): ConferenceStatus {
  if (today < conference.starts_on) return "upcoming";
  if (today > conference.ends_on) return "past";
  return "current";
}

/** The historical hostname keeps serving AAIC at its root path. */
const LEGACY_HOST_CONFERENCES: Readonly<Record<string, string>> = {
  "aaic2026.kozak.ch": "aaic-2026",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requiredString(
  record: Record<string, unknown>,
  key: string,
  path: string,
  pattern?: RegExp,
): string {
  const value = record[key];
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    (pattern && !pattern.test(value))
  ) {
    throw new Error(`${path}.${key} is invalid`);
  }
  return value;
}
