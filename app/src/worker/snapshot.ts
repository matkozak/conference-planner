import type { Note, NotebookSnapshot, Rsvp } from "../shared/notebook";

/** Build the portable notebook backup consumed by the refresh checker. */
export function notebookSnapshot(
  programVersion: string,
  notes: Note[],
  rsvps: Rsvp[],
  exportedAt = new Date().toISOString(),
): NotebookSnapshot {
  return {
    program_version: programVersion,
    exported_at: exportedAt,
    notes,
    rsvps,
  };
}
