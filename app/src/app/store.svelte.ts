/**
 * Central app state, Elm-ish: one reactive `ui` object, plain functions as
 * the only way to change it, hash-based routing as the source of navigation
 * truth. The program itself is immutable, so its indexes are plain Maps
 * built once at load.
 */
import UFuzzy from "@leeoniya/ufuzzy";

import { PROGRAM_PATH } from "../shared/generated/program-meta";
import type { Presentation, Program, Session } from "../shared/types";
import { displayTitle, localToday } from "./format";

export type Route =
  | { view: "day"; day: string }
  | { view: "session"; id: string; talk?: string }
  | { view: "posters" }
  | { view: "me" };

export const ui = $state({
  program: null as Program | null,
  route: null as Route | null,
  error: "",
});

/** Search inputs live here (not in components) so browser/app back keeps them. */
export const searchState = $state({ query: "", posters: "" });

// --- Immutable program indexes (filled once by init) ---

export const sessionsById = new Map<string, Session>();
/** Any item id (session or talk) → the entry that resolves it. */
export const itemsById = new Map<string, SearchEntry>();
/** Non-poster sessions per day: the daily program. */
export const sessionsByDay = new Map<string, Session[]>();
/** Poster sessions per day: shown in the Posters tab. */
export const posterSessionsByDay = new Map<string, Session[]>();

export function isPosterSession(s: Session): boolean {
  return s.category === "Poster";
}

// --- Init & routing ---

// Scroll positions per hash so back/up navigation restores where you were.
const scrollPositions = new Map<string, number>();
let currentHash = "";

// In-app back stack of previous hashes, deduped: navigating to a page that is
// already on the stack truncates back to it, so day ↔ session ping-pong can't
// grow the stack or trap the user in a loop ("unique previous").
const backStack: string[] = [];

export function savedScroll(hash: string): number {
  return scrollPositions.get(hash) ?? 0;
}

export async function init(): Promise<void> {
  currentHash = location.hash;
  window.addEventListener("hashchange", () => {
    scrollPositions.set(currentHash, window.scrollY);
    const previous = currentHash;
    currentHash = location.hash;
    const seenAt = backStack.lastIndexOf(currentHash);
    if (seenAt >= 0) backStack.length = seenAt;
    else if (previous && previous !== currentHash) backStack.push(previous);
    ui.route = parseHash();
  });
  try {
    const res = await fetch(PROGRAM_PATH);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const program: Program = await res.json();
    buildIndexes(program);
    ui.program = program;
  } catch (err) {
    ui.error = `Failed to load the program: ${err instanceof Error ? err.message : String(err)}`;
    return;
  }
  ui.route = parseHash();
}

function parseHash(): Route {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "s" && parts[1] && sessionsById.has(parts[1])) {
    return { view: "session", id: parts[1], talk: parts[2] };
  }
  if (parts[0] === "posters") return { view: "posters" };
  if (parts[0] === "me") return { view: "me" };
  if (parts[0] === "day" && parts[1] && sessionsByDay.has(parts[1])) {
    return { view: "day", day: parts[1] };
  }
  return { view: "day", day: initialDay() };
}

export function gotoDay(day: string): void {
  rememberDay(day);
  location.hash = `#/day/${day}`;
}

export function gotoSession(id: string, talk?: string): void {
  location.hash = talk ? `#/s/${id}/${talk}` : `#/s/${id}`;
}

export function gotoPosters(): void {
  location.hash = "#/posters";
}

export function gotoMe(): void {
  location.hash = "#/me";
}

export function gotoHome(): void {
  location.hash = `#/day/${initialDay()}`;
}

/**
 * The header arrow: return to the unique previous in-app page. Falls back to
 * hierarchy-up (goUp) when there is no previous page, e.g. on a shared deep
 * link. The browser back button keeps its native history semantics.
 */
export function goBack(): void {
  const previous = backStack[backStack.length - 1];
  // The hashchange handler recognizes the revisit and truncates the stack.
  if (previous !== undefined) location.hash = previous;
  else goUp();
}

/**
 * Up one level in the hierarchy: a session belongs to its day (or to the
 * Posters tab for poster sessions); everything else goes home.
 */
export function goUp(): void {
  const route = ui.route;
  if (route?.view === "session") {
    const session = sessionsById.get(route.id);
    if (session && isPosterSession(session)) gotoPosters();
    else if (session) gotoDay(session.date);
    else gotoHome();
  } else {
    gotoHome();
  }
}

// --- Day stickiness: an explicit choice wins for the rest of that real day,
// --- then we default back to "today at the conference".

const DAY_KEY = "aaic:day";

function rememberDay(day: string): void {
  localStorage.setItem(DAY_KEY, JSON.stringify({ day, on: localToday() }));
}

function initialDay(): string {
  const days = ui.program?.days ?? [];
  const today = localToday();
  try {
    const stored: unknown = JSON.parse(localStorage.getItem(DAY_KEY) ?? "null");
    if (
      typeof stored === "object" &&
      stored !== null &&
      "day" in stored &&
      "on" in stored &&
      stored.on === today &&
      typeof stored.day === "string" &&
      days.includes(stored.day)
    ) {
      return stored.day;
    }
  } catch {
    // corrupted localStorage — fall through to the default
  }
  if (days.includes(today)) return today;
  const first = days[0];
  const last = days[days.length - 1];
  if (!first || !last) return today;
  return today < first ? first : last;
}

// --- People ---

export function speakerNames(item: Presentation): string[] {
  const people = ui.program?.people ?? {};
  return (item.speaker_ids ?? []).flatMap((id) => {
    const p = people[id];
    return p ? [p.name] : [];
  });
}

// --- Fuzzy search over sessions, talks, and posters ---

export type EntryKind = "session" | "posters" | "talk" | "poster";

export interface SearchEntry {
  session: Session;
  talk?: Presentation;
}

export function entryKind(entry: SearchEntry): EntryKind {
  const poster = isPosterSession(entry.session);
  if (entry.talk) return poster ? "poster" : "talk";
  return poster ? "posters" : "session";
}

const haystack: string[] = [];
const searchEntries: SearchEntry[] = [];
const uf = new UFuzzy({ intraMode: 1 });

function buildIndexes(program: Program): void {
  const byStart = (a: Session, b: Session) =>
    (a.starts_at ?? "").localeCompare(b.starts_at ?? "") ||
    a.title.localeCompare(b.title);

  for (const day of program.days) {
    sessionsByDay.set(day, []);
    posterSessionsByDay.set(day, []);
  }
  for (const s of [...program.sessions].sort(byStart)) {
    sessionsById.set(s.id, s);
    const dayMap = isPosterSession(s) ? posterSessionsByDay : sessionsByDay;
    dayMap.get(s.date)?.push(s);
  }
  // Drop days that have no poster sessions at all (keeps the tab tidy).
  for (const [day, list] of posterSessionsByDay) {
    if (list.length === 0) posterSessionsByDay.delete(day);
  }

  const names = (ids?: string[]) =>
    (ids ?? [])
      .map((id) => program.people[id]?.name)
      .filter(Boolean)
      .join(" ");
  for (const s of sessionsById.values()) {
    haystack.push(
      [displayTitle(s), s.category, s.location, names(s.speaker_ids)]
        .filter(Boolean)
        .join(" | "),
    );
    searchEntries.push({ session: s });
    itemsById.set(s.id, { session: s });
    for (const t of s.presentations) {
      haystack.push(
        [t.title, t.location, names(t.speaker_ids)].filter(Boolean).join(" | "),
      );
      searchEntries.push({ session: s, talk: t });
      itemsById.set(t.id, { session: s, talk: t });
    }
  }
}

/**
 * Fuzzy search, uFuzzy-ranked (the 10_000 infoThresh exceeds the haystack
 * size, so ranking always runs). With `preferDay`, matches on that day rise
 * above the rest, keeping rank order within each group.
 */
export function search(
  query: string,
  limit = 40,
  scope: "all" | "posters" = "all",
  preferDay?: string,
): SearchEntry[] {
  const q = query.trim();
  if (q.length < 2) return [];
  const [idxs, info, order] = uf.search(haystack, q, 1, 10_000);
  if (!idxs?.length) return [];
  const ranked = order && info ? order.map((i) => info.idx[i] ?? 0) : [...idxs];
  const out: SearchEntry[] = [];
  for (const i of ranked) {
    const entry = searchEntries[i];
    if (!entry) continue;
    if (scope === "posters" && entryKind(entry) !== "poster") continue;
    out.push(entry);
    if (out.length >= limit * 2) break; // headroom for the preferDay partition
  }
  if (preferDay) {
    const here = out.filter((e) => e.session.date === preferDay);
    const elsewhere = out.filter((e) => e.session.date !== preferDay);
    return [...here, ...elsewhere].slice(0, limit);
  }
  return out.slice(0, limit);
}
