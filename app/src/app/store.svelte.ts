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
  | { view: "session"; id: string }
  | { view: "search" };

export const ui = $state({
  program: null as Program | null,
  route: null as Route | null,
  error: "",
});

// --- Immutable program indexes (filled once by init) ---

export const sessionsById = new Map<string, Session>();
export const sessionsByDay = new Map<string, Session[]>();

// --- Init & routing ---

// One-level back target within the app. We track it ourselves because
// history.back() could leave the SPA (e.g. to the Access login redirect)
// when a session was opened via a shared deep link.
let backHash: string | null = null;
let currentHash = "";

export async function init(): Promise<void> {
  currentHash = location.hash;
  window.addEventListener("hashchange", () => {
    backHash = currentHash;
    currentHash = location.hash;
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
    return { view: "session", id: parts[1] };
  }
  if (parts[0] === "search") return { view: "search" };
  if (parts[0] === "day" && parts[1] && sessionsByDay.has(parts[1])) {
    return { view: "day", day: parts[1] };
  }
  return { view: "day", day: initialDay() };
}

export function gotoDay(day: string): void {
  rememberDay(day);
  location.hash = `#/day/${day}`;
}

export function gotoSession(id: string): void {
  location.hash = `#/s/${id}`;
}

export function gotoSearch(): void {
  location.hash = "#/search";
}

export function goBack(): void {
  if (backHash !== null && backHash !== location.hash) location.hash = backHash;
  else location.hash = `#/day/${initialDay()}`;
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

// --- Fuzzy search over sessions and talks ---

export interface SearchEntry {
  session: Session;
  talk?: Presentation;
}

const haystack: string[] = [];
const searchEntries: SearchEntry[] = [];
const uf = new UFuzzy({ intraMode: 1 });

function buildIndexes(program: Program): void {
  const byStart = (a: Session, b: Session) =>
    (a.starts_at ?? "").localeCompare(b.starts_at ?? "") ||
    a.title.localeCompare(b.title);

  for (const day of program.days) sessionsByDay.set(day, []);
  for (const s of [...program.sessions].sort(byStart)) {
    sessionsById.set(s.id, s);
    sessionsByDay.get(s.date)?.push(s);
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
    for (const t of s.presentations) {
      haystack.push(
        [t.title, t.location, names(t.speaker_ids)].filter(Boolean).join(" | "),
      );
      searchEntries.push({ session: s, talk: t });
    }
  }
}

export function search(query: string, limit = 40): SearchEntry[] {
  const q = query.trim();
  if (q.length < 2) return [];
  const [idxs, info, order] = uf.search(haystack, q, 1, 1000);
  if (!idxs?.length) return [];
  const ranked = order && info ? order.map((i) => info.idx[i] ?? 0) : [...idxs];
  return ranked.slice(0, limit).flatMap((i) => {
    const entry = searchEntries[i];
    return entry ? [entry] : [];
  });
}
