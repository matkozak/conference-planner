/**
 * Client-side notebook store. Connects to the NotebookDO via WebSocket,
 * maintains a reactive map of notes, reconnects with capped backoff.
 */
import { SvelteMap } from "svelte/reactivity";

import type { ClientMsg, Note, ServerMsg } from "../shared/notebook";

export const notes = $state({
  byId: new SvelteMap<number, Note>(),
  connected: false,
});

/** item_id → sorted author emails who said "I'll be there". */
export const rsvps = new SvelteMap<string, string[]>();

/** Current user email — refreshed from /api/health on every (re)connect. */
export const currentUser = $state({ email: "" });

let ws: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let reconnectDelay = 2_000;
const MAX_RECONNECT_DELAY = 30_000;

export function notesFor(itemId: string): Note[] {
  return [...notes.byId.values()]
    .filter((n) => n.item_id === itemId)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
}

export function rsvpAuthors(itemId: string): string[] {
  return rsvps.get(itemId) ?? [];
}

export function myRsvp(itemId: string): boolean {
  return rsvpAuthors(itemId).includes(currentUser.email);
}

/** Apply one rsvp change locally (fresh array — SvelteMap tracks by key). */
function applyRsvp(itemId: string, author: string, going: boolean): void {
  const authors = (rsvps.get(itemId) ?? []).filter((a) => a !== author);
  if (going) authors.push(author);
  if (authors.length > 0) rsvps.set(itemId, authors.sort());
  else rsvps.delete(itemId);
}

export function connectNotebook(): void {
  void refreshIdentity();
  openSocket();
}

async function refreshIdentity(): Promise<void> {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) return; // keep the previous identity rather than degrading
    const data: { user: string | null } = await res.json();
    if (data.user) currentUser.email = data.user;
  } catch {
    // offline — keep whatever identity we had
  }
}

function openSocket(): void {
  if (
    ws &&
    (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)
  )
    return;

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/api/ws`);

  ws.onopen = () => {
    notes.connected = true;
    reconnectDelay = 2_000;
    // The Access session may have rotated while we were disconnected.
    if (!currentUser.email) void refreshIdentity();
  };

  ws.onmessage = (ev: MessageEvent) => {
    const msg: ServerMsg = JSON.parse(String(ev.data));
    switch (msg.type) {
      case "snapshot":
        notes.byId.clear();
        for (const n of msg.notes) notes.byId.set(n.id, n);
        rsvps.clear();
        for (const r of msg.rsvps) applyRsvp(r.item_id, r.author, true);
        break;
      case "note:upserted":
        notes.byId.set(msg.note.id, msg.note);
        break;
      case "note:deleted":
        notes.byId.delete(msg.id);
        break;
      case "rsvp:set":
        applyRsvp(msg.item_id, msg.author, msg.going);
        break;
      case "error":
        console.warn("Notebook error:", msg.message);
        break;
    }
  };

  ws.onclose = () => {
    notes.connected = false;
    scheduleReconnect();
  };
  ws.onerror = () => ws?.close();
}

function scheduleReconnect(): void {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    openSocket();
  }, reconnectDelay);
  reconnectDelay = Math.min(reconnectDelay * 2, MAX_RECONNECT_DELAY);
}

function send(msg: ClientMsg): void {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
  }
}

export function createNote(itemId: string, body: string): void {
  send({ type: "note:create", item_id: itemId, body });
}

export function updateNote(id: number, body: string): void {
  send({ type: "note:update", id, body });
}

export function deleteNote(id: number): void {
  send({ type: "note:delete", id });
}

export function setRsvp(itemId: string, going: boolean): void {
  send({ type: "rsvp:set", item_id: itemId, going });
}
