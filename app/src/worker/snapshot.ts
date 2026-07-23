import type { Note, NotebookSnapshot, Rsvp } from "../shared/notebook";

/** Build the portable notebook backup consumed by the refresh checker. */
export function notebookSnapshot(
  conferenceId: string,
  programVersion: string,
  notes: Note[],
  rsvps: Rsvp[],
  exportedAt = new Date().toISOString(),
): NotebookSnapshot {
  return {
    conference_id: conferenceId,
    program_version: programVersion,
    exported_at: exportedAt,
    notes,
    rsvps,
  };
}
