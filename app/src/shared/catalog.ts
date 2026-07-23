import {
  PROGRAM_CONFERENCE,
  PROGRAM_HASH,
  PROGRAM_PATH,
} from "./generated/program-meta";
import type { Conference } from "./program";

export interface ConferenceCatalogEntry extends Conference {
  program_hash: string;
  program_path: string;
}

/** Checked-in bridge to the private R2 catalog planned for publication. */
export const CONFERENCE_CATALOG = [
  {
    ...PROGRAM_CONFERENCE,
    program_hash: PROGRAM_HASH,
    program_path: PROGRAM_PATH,
  },
] satisfies readonly ConferenceCatalogEntry[];

const conferencesById = new Map<string, ConferenceCatalogEntry>(
  CONFERENCE_CATALOG.map((conference) => [conference.id, conference]),
);

/** The historical hostname keeps serving AAIC at its root path. */
const LEGACY_HOST_CONFERENCES: Readonly<Record<string, string>> = {
  "aaic2026.kozak.ch": "aaic-2026",
};

export function conferenceById(id: string): ConferenceCatalogEntry | undefined {
  return conferencesById.get(id);
}

/**
 * Resolve a browser pathname to a finite catalog entry.
 *
 * null means the catalog root; undefined means an invalid/unknown path.
 */
export function conferenceForLocation(
  pathname: string,
  hostname: string,
): ConferenceCatalogEntry | null | undefined {
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length === 0) {
    const legacyId = LEGACY_HOST_CONFERENCES[hostname];
    return legacyId ? conferenceById(legacyId) : null;
  }
  if (parts.length !== 1) return undefined;
  return conferenceById(parts[0] ?? "");
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
