import { Hono } from "hono";

// Re-export the DO class so wrangler can discover it.
export { NotebookDO } from "./notebook";
import type { NotebookDO } from "./notebook";
import { PROGRAM_PATH } from "../shared/generated/program-meta";
import type { Program } from "../shared/types";
import { notebookSnapshot } from "./snapshot";

// The generated Env has NOTEBOOK: DurableObjectNamespace (untyped).
// Augment it so stubs expose RPC methods.
declare global {
  interface Env {
    NOTEBOOK: DurableObjectNamespace<NotebookDO>;
  }
}

/**
 * The Worker only handles /api/* (see run_worker_first in wrangler.jsonc);
 * everything else is served from static assets, with SPA fallback.
 */
const app = new Hono<{ Bindings: Env }>();

/** Extracts the verified Access email (or "anonymous" in local dev). */
function userEmail(c: {
  req: { header(name: string): string | undefined };
}): string {
  return c.req.header("Cf-Access-Authenticated-User-Email") ?? "anonymous";
}

app.get("/api/health", (c) => c.json({ ok: true, user: userEmail(c) }));

// --- Notebook WebSocket upgrade ---
app.get("/api/ws", (c) => {
  if (c.req.header("Upgrade") !== "websocket") {
    return c.text("Expected WebSocket upgrade", 426);
  }
  const stub = c.env.NOTEBOOK.getByName("team");
  // Forward the request with the user email attached so the DO can read it.
  const headers = new Headers(c.req.raw.headers);
  headers.set("X-User-Email", userEmail(c));
  return stub.fetch(new Request(c.req.url, { headers }));
});

// --- Notes-only read endpoint (the client currently reconnects via WebSocket) ---
app.get("/api/notes", async (c) => {
  const stub = c.env.NOTEBOOK.getByName("team");
  const notes = await stub.getAllNotes();
  return c.json(notes);
});

// --- Portable backup + refresh-safety input (the whole app is Access-protected) ---
app.get("/api/notebook/export.json", async (c) => {
  const stub = c.env.NOTEBOOK.getByName("team");
  const [notes, rsvps, program] = await Promise.all([
    stub.getAllNotes(),
    stub.getAllRsvps(),
    c.env.ASSETS.fetch(new URL(PROGRAM_PATH, c.req.url)).then(
      (response) => response.json() as Promise<Program>,
    ),
  ]);
  return c.json(notebookSnapshot(program.version, notes, rsvps), 200, {
    "Content-Disposition": `attachment; filename="aaic2026-notebook-${new Date().toISOString().slice(0, 10)}.json"`,
  });
});

// --- CSV export of all notes joined with program item titles ---
app.get("/api/notes/export", async (c) => {
  const stub = c.env.NOTEBOOK.getByName("team");
  const [notes, program] = await Promise.all([
    stub.getAllNotes(),
    c.env.ASSETS.fetch(new URL(PROGRAM_PATH, c.req.url)).then(
      (r) => r.json() as Promise<Program>,
    ),
  ]);

  // item id → its title and the title of the containing session
  const titles = new Map<string, { item: string; session: string }>();
  for (const s of program.sessions) {
    titles.set(s.id, { item: s.title, session: s.title });
    for (const t of s.presentations) {
      titles.set(t.id, { item: t.title, session: s.title });
    }
  }

  const csvHeader =
    "id,item_id,item_title,session_title,author,body,created_at,updated_at";
  const escape = (s: string) => `"${s.replace(/"/g, '""')}"`;
  const rows = notes.map((n) => {
    const t = titles.get(n.item_id);
    return [
      n.id,
      escape(n.item_id),
      escape(t?.item ?? ""),
      escape(t?.session ?? ""),
      escape(n.author),
      escape(n.body),
      n.created_at,
      n.updated_at,
    ].join(",");
  });

  // UTF-8 BOM so Excel decodes correctly (this team will write "Aβ")
  return c.body("\u{FEFF}" + [csvHeader, ...rows].join("\r\n"), 200, {
    "Content-Type": "text/csv; charset=utf-8",
    "Content-Disposition": `attachment; filename="aaic2026-notes-${new Date().toISOString().slice(0, 10)}.csv"`,
  });
});

export default app;
