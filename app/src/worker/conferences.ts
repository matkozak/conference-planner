import { conferenceById, type ConferenceCatalogEntry } from "../shared/catalog";

export interface RuntimeConference {
  catalog: ConferenceCatalogEntry;
  notebook_name: string;
}

/**
 * Temporary storage aliases used only while a conference notebook is migrated.
 * New conferences default to their catalog id.
 */
const LEGACY_NOTEBOOK_NAMES: Readonly<Record<string, string>> = {
  "aaic-2026": "team",
};

/** Resolve user input through the finite catalog before selecting a DO. */
export function runtimeConference(id: string): RuntimeConference | undefined {
  const catalog = conferenceById(id);
  if (!catalog) return undefined;
  return {
    catalog,
    notebook_name: LEGACY_NOTEBOOK_NAMES[id] ?? catalog.id,
  };
}
