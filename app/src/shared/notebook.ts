/** Wire protocol for the Notebook WebSocket + REST fallback. */

export interface Note {
  id: number;
  item_id: string;
  author: string;
  body: string;
  created_at: string;
  updated_at: string;
}

// --- Client → server messages ---

export type ClientMsg =
  | { type: "note:create"; item_id: string; body: string }
  | { type: "note:update"; id: number; body: string }
  | { type: "note:delete"; id: number };

// --- Server → client messages ---

export type ServerMsg =
  | { type: "snapshot"; notes: Note[] }
  | { type: "note:upserted"; note: Note }
  | { type: "note:deleted"; id: number }
  | { type: "error"; message: string };
