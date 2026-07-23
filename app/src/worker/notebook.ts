import { DurableObject } from "cloudflare:workers";

import type { ClientMsg, ServerMsg } from "../shared/notebook";

/** Row shape returned by SQLite — matches Note but satisfies SqlStorageValue. */
type NoteRow = Record<string, SqlStorageValue> & {
  id: number;
  item_id: string;
  author: string;
  body: string;
  created_at: string;
  updated_at: string;
};

type RsvpRow = Record<string, SqlStorageValue> & {
  item_id: string;
  author: string;
};

/**
 * One conference team's shared notebook. Each named instance holds every note
 * and RSVP for that conference. SQLite for storage, WebSocket hibernation for
 * live sync.
 *
 * Each WebSocket carries the user's email as an attachment, set once at accept
 * time from the Access JWT validated by the outer Worker.
 */
export class NotebookDO extends DurableObject<Env> {
  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    ctx.blockConcurrencyWhile(async () => {
      ctx.storage.sql.exec(`
        CREATE TABLE IF NOT EXISTS notes (
          id         INTEGER PRIMARY KEY AUTOINCREMENT,
          item_id    TEXT    NOT NULL,
          author     TEXT    NOT NULL,
          body       TEXT    NOT NULL,
          created_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
          updated_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        )
      `);
      ctx.storage.sql.exec(`
        CREATE INDEX IF NOT EXISTS idx_notes_item ON notes(item_id)
      `);
      ctx.storage.sql.exec(`
        CREATE TABLE IF NOT EXISTS rsvps (
          item_id    TEXT NOT NULL,
          author     TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
          PRIMARY KEY (item_id, author)
        )
      `);
    });
  }

  // --- Read methods used by WebSocket snapshots and exports ---

  async getAllNotes(): Promise<NoteRow[]> {
    return this.ctx.storage.sql
      .exec<NoteRow>("SELECT * FROM notes ORDER BY created_at")
      .toArray();
  }

  async getAllRsvps(): Promise<RsvpRow[]> {
    return this.ctx.storage.sql
      .exec<RsvpRow>("SELECT item_id, author FROM rsvps ORDER BY created_at")
      .toArray();
  }

  // --- WebSocket lifecycle ---

  override async fetch(request: Request): Promise<Response> {
    if (request.headers.get("Upgrade") !== "websocket") {
      return new Response("Expected WebSocket", { status: 426 });
    }
    const author = request.headers.get("X-User-Email");
    if (!author) {
      // The Worker always sets this after auth; absence is a caller bug.
      return new Response("Missing X-User-Email", { status: 403 });
    }
    const pair = new WebSocketPair();
    const [client, server] = [pair[0], pair[1]];
    this.ctx.acceptWebSocket(server);
    server.serializeAttachment({ author });

    // Send current snapshot
    const notes = await this.getAllNotes();
    const rsvps = await this.getAllRsvps();
    const msg: ServerMsg = { type: "snapshot", notes, rsvps };
    server.send(JSON.stringify(msg));

    return new Response(null, { status: 101, webSocket: client });
  }

  override async webSocketMessage(
    ws: WebSocket,
    message: string | ArrayBuffer,
  ): Promise<void> {
    if (typeof message !== "string") return;
    const attachment = ws.deserializeAttachment() as { author?: string } | null;
    if (!attachment?.author) {
      // Post-auth an identity can never legitimately be absent; close instead
      // of inventing an "anonymous" author that would confuse ownership checks.
      ws.close(1011, "Missing identity");
      return;
    }
    const author = attachment.author;
    let parsed: ClientMsg;
    try {
      parsed = JSON.parse(message) as ClientMsg;
    } catch {
      this.sendTo(ws, { type: "error", message: "Invalid JSON" });
      return;
    }
    switch (parsed.type) {
      case "note:create":
        this.handleCreate(parsed.item_id, parsed.body, author);
        break;
      case "note:update":
        this.handleUpdate(parsed.id, parsed.body, author);
        break;
      case "note:delete":
        this.handleDelete(parsed.id, author);
        break;
      case "rsvp:set":
        this.handleRsvpSet(parsed.item_id, parsed.going, author);
        break;
      default:
        this.sendTo(ws, { type: "error", message: "Unknown message type" });
    }
  }

  // No webSocketClose override: the web_socket_auto_reply_to_close compat
  // flag (default on our compatibility_date) completes the close handshake,
  // and re-calling ws.close() with client-supplied 1005/1006 codes throws.

  override async webSocketError(_ws: WebSocket, error: unknown): Promise<void> {
    console.error(
      "WebSocket error:",
      error instanceof Error ? error.message : String(error),
    );
  }

  // --- Handlers ---

  private handleCreate(item_id: string, body: string, author: string): void {
    const trimmed = body.trim();
    if (!trimmed || !item_id) return;
    const note = this.ctx.storage.sql
      .exec<NoteRow>(
        `INSERT INTO notes (item_id, author, body) VALUES (?, ?, ?)
         RETURNING *`,
        item_id,
        author,
        trimmed,
      )
      .one();
    this.broadcast({ type: "note:upserted", note });
  }

  private handleUpdate(id: number, body: string, author: string): void {
    const trimmed = body.trim();
    if (!trimmed) return;
    const rows = this.ctx.storage.sql
      .exec<NoteRow>(
        `UPDATE notes SET body = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
         WHERE id = ? AND author = ?
         RETURNING *`,
        trimmed,
        id,
        author,
      )
      .toArray();
    if (rows[0]) this.broadcast({ type: "note:upserted", note: rows[0] });
  }

  private handleDelete(id: number, author: string): void {
    const deleted = this.ctx.storage.sql
      .exec(
        "DELETE FROM notes WHERE id = ? AND author = ? RETURNING id",
        id,
        author,
      )
      .toArray();
    if (deleted.length > 0) {
      this.broadcast({ type: "note:deleted", id });
    }
  }

  /** Idempotent toggle; broadcasts only when the state actually changed. */
  private handleRsvpSet(item_id: string, going: boolean, author: string): void {
    if (!item_id) return;
    const changed = this.ctx.storage.sql
      .exec(
        going
          ? `INSERT INTO rsvps (item_id, author) VALUES (?, ?)
             ON CONFLICT DO NOTHING RETURNING item_id`
          : "DELETE FROM rsvps WHERE item_id = ? AND author = ? RETURNING item_id",
        item_id,
        author,
      )
      .toArray();
    if (changed.length > 0) {
      this.broadcast({ type: "rsvp:set", item_id, author, going });
    }
  }

  // --- Broadcast to all connected clients ---

  private broadcast(msg: ServerMsg): void {
    const payload = JSON.stringify(msg);
    for (const ws of this.ctx.getWebSockets()) {
      try {
        ws.send(payload);
      } catch {
        // Client disconnected between getWebSockets() and send()
      }
    }
  }

  private sendTo(ws: WebSocket, msg: ServerMsg): void {
    try {
      ws.send(JSON.stringify(msg));
    } catch {
      // Already closed
    }
  }
}
