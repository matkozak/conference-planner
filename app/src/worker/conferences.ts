import { conferenceById, type ConferenceCatalogEntry } from "../shared/catalog";

export interface RuntimeConference {
  catalog: ConferenceCatalogEntry;
  notebook_name: string;
}

/** Resolve user input through the finite catalog before selecting a DO. */
export function runtimeConference(id: string): RuntimeConference | undefined {
  const catalog = conferenceById(id);
  if (!catalog) return undefined;
  return {
    catalog,
    notebook_name: catalog.id,
  };
}
