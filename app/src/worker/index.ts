import { Hono } from "hono";

// Re-export the DO class so wrangler can discover it.
export { NotebookDO } from "./notebook";
import type { NotebookDO } from "./notebook";
import { conferenceById } from "../shared/catalog";
import type { ConferenceProgram } from "../shared/program";
import { accessAuth, type AppEnv } from "./access";
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
const app = new Hono<AppEnv>();

// Auth by default on every worker-served path (today only /api/* reaches the
// Worker, per run_worker_first) so a future route can't ship unauthenticated.
app.use("*", accessAuth);

app.get("/api/health", (c) => c.json({ ok: true, user: c.get("userEmail") }));

// --- Conference-scoped notebook WebSocket upgrade ---
app.get("/api/conferences/:conferenceId/ws", (c) => {
  const conference = conferenceById(c.req.param("conferenceId"));
  if (!conference) return c.notFound();
  if (c.req.header("Upgrade") !== "websocket") {
    return c.text("Expected WebSocket upgrade", 426);
  }
  const stub = c.env.NOTEBOOK.getByName(conference.id);
  // Forward the request with the user email attached so the DO can read it.
  const headers = new Headers(c.req.raw.headers);
  headers.set("X-User-Email", c.get("userEmail"));
  return stub.fetch(new Request(c.req.url, { headers }));
});

// --- Portable backup + refresh-safety input (the whole app is Access-protected) ---
app.get("/api/conferences/:conferenceId/notebook/export.json", async (c) => {
  const conference = conferenceById(c.req.param("conferenceId"));
  if (!conference) return c.notFound();
  const stub = c.env.NOTEBOOK.getByName(conference.id);
  const [notes, rsvps] = await Promise.all([
    stub.getAllNotes(),
    stub.getAllRsvps(),
  ]);
  return c.json(
    notebookSnapshot(conference.id, conference.program_hash, notes, rsvps),
    200,
    {
      "Content-Disposition": `attachment; filename="${conference.id}-notebook-${new Date().toISOString().slice(0, 10)}.json"`,
    },
  );
});

// --- CSV export of all notes joined with program item titles ---
app.get("/api/conferences/:conferenceId/notes/export.csv", async (c) => {
  const conference = conferenceById(c.req.param("conferenceId"));
  if (!conference) return c.notFound();
  const stub = c.env.NOTEBOOK.getByName(conference.id);
  const [notes, program] = await Promise.all([
    stub.getAllNotes(),
    c.env.ASSETS.fetch(new URL(conference.program_path, c.req.url)).then(
      (r) => r.json() as Promise<ConferenceProgram>,
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
    "Content-Disposition": `attachment; filename="${conference.id}-notes-${new Date().toISOString().slice(0, 10)}.csv"`,
  });
});

export default app;
