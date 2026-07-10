/** Wire protocol for the Notebook WebSocket and portable snapshot export. */

export interface Note {
  id: number;
  item_id: string;
  author: string;
  body: string;
  created_at: string;
  updated_at: string;
}

/** One "I'll be there" mark. Keyed by (item_id, author) — no id needed. */
export interface Rsvp {
  item_id: string;
  author: string;
}

/** Downloadable safety snapshot used before a program refresh. */
export interface NotebookSnapshot {
  program_version: string;
  exported_at: string;
  notes: Note[];
  rsvps: Rsvp[];
}

// --- Client → server messages ---

export type ClientMsg =
  | { type: "note:create"; item_id: string; body: string }
  | { type: "note:update"; id: number; body: string }
  | { type: "note:delete"; id: number }
  | { type: "rsvp:set"; item_id: string; going: boolean };

// --- Server → client messages ---

export type ServerMsg =
  | { type: "snapshot"; notes: Note[]; rsvps: Rsvp[] }
  | { type: "note:upserted"; note: Note }
  | { type: "note:deleted"; id: number }
  | { type: "rsvp:set"; item_id: string; author: string; going: boolean }
  | { type: "error"; message: string };
