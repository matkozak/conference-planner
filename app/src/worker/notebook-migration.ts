import type { Note, Rsvp } from "../shared/notebook";

export const AAIC_NOTEBOOK_MIGRATION = {
  conference_id: "aaic-2026",
  source: "team",
  destination: "aaic-2026",
  confirm: "copy production notebook",
} as const;

export interface NotebookRows {
  notes: Note[];
  rsvps: Rsvp[];
}

export interface NotebookMigrationStatus {
  read_only: boolean;
  note_count: number;
  rsvp_count: number;
}

export function isAaicMigrationConfirmation(value: unknown): boolean {
  if (typeof value !== "object" || value === null) return false;
  return Object.entries(AAIC_NOTEBOOK_MIGRATION).every(
    ([key, expected]) =>
      key in value && (value as Record<string, unknown>)[key] === expected,
  );
}

export function notebookRowsEqual(
  left: NotebookRows,
  right: NotebookRows,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}
