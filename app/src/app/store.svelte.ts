/**
 * Central app state, Elm-ish: one reactive `ui` object, plain functions as
 * the only way to change it, hash-based routing as the source of navigation
 * truth. The program itself is immutable, so its indexes are plain Maps
 * built once at load.
 */
import UFuzzy from "@leeoniya/ufuzzy";

import {
  conferenceForLocation,
  parseConferenceCatalog,
  programPath,
  type ConferenceCatalogEntry,
} from "../shared/catalog";
import type {
  ConferenceProgram,
  Presentation,
  Session,
} from "../shared/program";
import { todayInTimeZone } from "./format";
import { visibleDays } from "./schedule";
import { setVenueTimeZone } from "./tz.svelte";

export type Route =
  | { view: "day"; day: string }
  | { view: "session"; id: string; talk?: string }
  | { view: "posters" }
  | { view: "search" }
  | { view: "team"; tab: PlanTab }
  | { view: "me"; tab: PlanTab };

/** Segments within the Me and Team views. */
export type PlanTab = "talks" | "posters" | "notes";

export const ui = $state({
  catalog: null as ConferenceCatalogEntry[] | null,
  program: null as ConferenceProgram | null,
  route: null as Route | null,
  error: "",
});

/**
 * Search inputs live here (not in components) so browser/app back keeps them.
 * `query` is shared between day views and the Search tab: typing on a day and
 * then opening Search carries the query over (the "widen" gesture).
 */
export const searchState = $state({
  query: "",
  posters: "",
  inAbstracts: false,
});

// --- Immutable program indexes (filled once by init) ---

export const sessionsById = new Map<string, Session>();
/** Any item id (session or talk) → the entry that resolves it. */
export const itemsById = new Map<string, SearchEntry>();
/** Non-poster sessions per day: the daily program. */
export const sessionsByDay = new Map<string, Session[]>();
/** Poster sessions per day: shown in the Posters tab. */
export const posterSessionsByDay = new Map<string, Session[]>();

export function isPosterSession(s: Session): boolean {
  return s.kind === "poster-session";
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

/** Initialize either the conference catalog root or one conference app. */
export async function init(): Promise<boolean> {
  try {
    const catalogResponse = await fetch("/api/catalog");
    if (!catalogResponse.ok) {
      throw new Error(`catalog HTTP ${catalogResponse.status}`);
    }
    const catalog = parseConferenceCatalog(await catalogResponse.json());
    const conference = conferenceForLocation(catalog, location.pathname);
    if (conference === null) {
      ui.catalog = catalog.conferences;
      document.title = "Conferences";
      return false;
    }
    if (!conference) {
      ui.error = "Conference not found.";
      return false;
    }

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

    const res = await fetch(programPath(conference));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const program: ConferenceProgram = await res.json();
    if (program.conference.id !== conference.id) {
      throw new Error(
        `catalog expected ${conference.id}, program contains ${program.conference.id}`,
      );
    }
    buildIndexes(program);
    setVenueTimeZone(program.conference.timezone, program.conference.starts_on);
    ui.program = program;
    document.title = program.conference.short_name;
  } catch (err) {
    ui.error = `Failed to load conference data: ${err instanceof Error ? err.message : String(err)}`;
    return false;
  }
  ui.route = parseHash();
  return true;
}

export function conferenceApiPath(path: string): string {
  const id = ui.program?.conference.id;
  if (!id) throw new Error("conference API requested before program load");
  return `/api/conferences/${encodeURIComponent(id)}${path}`;
}

function parseHash(): Route {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "s" && parts[1] && sessionsById.has(parts[1])) {
    return { view: "session", id: parts[1], talk: parts[2] };
  }
  if (parts[0] === "posters") return { view: "posters" };
  if (parts[0] === "search") return { view: "search" };
  if (parts[0] === "team") return { view: "team", tab: planTab(parts[1]) };
  if (parts[0] === "me") return { view: "me", tab: planTab(parts[1]) };
  if (parts[0] === "day" && parts[1] && sessionsByDay.has(parts[1])) {
    return { view: "day", day: parts[1] };
  }
  return { view: "day", day: initialDay() };
}

/** Hash segment → plan tab, defaulting to the primary Talks segment. */
function planTab(part: string | undefined): PlanTab {
  return part === "posters" || part === "notes" ? part : "talks";
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

export function gotoSearch(): void {
  location.hash = "#/search";
}

export function gotoTeam(tab: PlanTab = "talks"): void {
  location.hash = tab === "talks" ? "#/team" : `#/team/${tab}`;
}

export function gotoMe(tab: PlanTab = "talks"): void {
  location.hash = tab === "talks" ? "#/me" : `#/me/${tab}`;
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

const LEGACY_DAY_KEY = "aaic:day";

function dayKey(conferenceId: string): string {
  return `conferences:${conferenceId}:day`;
}

function conferenceToday(): string {
  return todayInTimeZone(ui.program?.conference.timezone ?? "UTC");
}

function rememberDay(day: string): void {
  const conferenceId = ui.program?.conference.id;
  if (!conferenceId) return;
  localStorage.setItem(
    dayKey(conferenceId),
    JSON.stringify({ day, on: conferenceToday() }),
  );
}

function initialDay(): string {
  const program = ui.program;
  const days = [...sessionsByDay.keys()];
  const today = conferenceToday();
  const key = program ? dayKey(program.conference.id) : "";
  const legacy =
    program?.conference.id === "aaic-2026"
      ? localStorage.getItem(LEGACY_DAY_KEY)
      : null;
  try {
    const stored: unknown = JSON.parse(
      (key && localStorage.getItem(key)) ?? legacy ?? "null",
    );
    if (
      typeof stored === "object" &&
      stored !== null &&
      "day" in stored &&
      "on" in stored &&
      stored.on === today &&
      typeof stored.day === "string" &&
      days.includes(stored.day)
    ) {
      if (key && !localStorage.getItem(key)) {
        localStorage.setItem(key, JSON.stringify(stored));
      }
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

export function speakerNames(item: Presentation | Session): string[] {
  const people = ui.program?.people ?? {};
  return (item.speaker_ids ?? []).flatMap((id) => {
    const p = people[id];
    return p ? [p.name] : [];
  });
}

/** "Name, Org" per primary speaker (talk detail); name alone if no org. */
export function speakerLines(item: Presentation | Session): string[] {
  const people = ui.program?.people ?? {};
  return (item.speaker_ids ?? []).flatMap((id) => {
    const p = people[id];
    if (!p) return [];
    return [p.org ? `${p.name}, ${p.org}` : p.name];
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
// Two-pass ranking: exact substring matches always beat typo-tolerant ones.
const ufExact = new UFuzzy();
const ufFuzzy = new UFuzzy({ intraMode: 1 });

function buildIndexes(program: ConferenceProgram): void {
  const byStart = (a: Session, b: Session) =>
    (a.starts_at ?? "").localeCompare(b.starts_at ?? "") ||
    a.title.localeCompare(b.title);

  const days = new Set(program.days);
  for (const session of program.sessions) {
    for (const day of visibleDays(session, program.conference.timezone))
      days.add(day);
  }
  for (const day of [...days].sort()) {
    sessionsByDay.set(day, []);
    posterSessionsByDay.set(day, []);
  }
  for (const s of [...program.sessions].sort(byStart)) {
    sessionsById.set(s.id, s);
    const dayMap = isPosterSession(s) ? posterSessionsByDay : sessionsByDay;
    for (const day of visibleDays(s, program.conference.timezone)) {
      dayMap.get(day)?.push(s);
    }
  }
  // Drop days that have no poster sessions at all (keeps the tab tidy).
  for (const [day, list] of posterSessionsByDay) {
    if (list.length === 0) posterSessionsByDay.delete(day);
  }

  // Primary-speaker names AND their organizations: "Roche" should find the
  // talks Roche people are giving, not rely on typo-luck against titles.
  const people = (ids?: string[]) =>
    (ids ?? [])
      .flatMap((id) => {
        const p = program.people[id];
        return p ? [p.name, p.org] : [];
      })
      .filter(Boolean)
      .join(" ");
  for (const s of sessionsById.values()) {
    haystack.push(
      [s.title, s.category, s.location, people(s.speaker_ids)]
        .filter(Boolean)
        .join(" | "),
    );
    searchEntries.push({ session: s });
    itemsById.set(s.id, { session: s });
    for (const t of s.presentations) {
      haystack.push(
        [t.title, t.location, people(t.speaker_ids)]
          .filter(Boolean)
          .join(" | "),
      );
      searchEntries.push({ session: s, talk: t });
      itemsById.set(t.id, { session: s, talk: t });
    }
  }
}

/** haystack + tag-stripped abstracts; built on first use of the toggle. */
let abstractHaystack: string[] | null = null;

function ensureAbstractHaystack(): string[] {
  abstractHaystack ??= searchEntries.map((e, i) => {
    const text = (e.talk ?? e.session).description_html ?? "";
    return `${haystack[i]} | ${text.replace(/<[^>]+>/g, " ")}`;
  });
  return abstractHaystack;
}

export interface SearchOptions {
  limit?: number;
  /** "posters" keeps only poster presentations. */
  scope?: "all" | "posters";
  /** Restrict to one conference day (day-view scoped search). */
  day?: string;
  /** Also match against abstract text (Search tab toggle). */
  abstracts?: boolean;
}

export interface RankedResults {
  entries: SearchEntry[];
  /** entries[0..exactCount) matched exactly; the rest are typo-tolerant. */
  exactCount: number;
}

function rankedIndexes(uf: UFuzzy, hs: string[], q: string): number[] {
  // infoThresh 10_000 exceeds the haystack size, so ranking always runs.
  const [idxs, info, order] = uf.search(hs, q, 1, 10_000);
  if (!idxs?.length) return [];
  return order && info ? order.map((i) => info.idx[i] ?? 0) : [...idxs];
}

/**
 * Two-pass search: exact substring matches first (uFuzzy-ranked), then —
 * only if there is room left — typo-tolerant matches as clearly-second-tier
 * backfill. `exactCount` lets the UI draw the line between the tiers.
 */
export function search(query: string, opts: SearchOptions = {}): RankedResults {
  const { limit = 40, scope = "all", day, abstracts = false } = opts;
  const q = query.trim();
  if (q.length < 2) return { entries: [], exactCount: 0 };
  const hs = abstracts ? ensureAbstractHaystack() : haystack;

  const keep = (e: SearchEntry) =>
    (scope !== "posters" || entryKind(e) === "poster") &&
    (day === undefined ||
      visibleDays(e.session, ui.program!.conference.timezone, e.talk).includes(
        day,
      ));

  const entries: SearchEntry[] = [];
  const seen = new Set<number>();
  const collect = (ranked: number[]) => {
    for (const i of ranked) {
      if (entries.length >= limit) return;
      if (seen.has(i)) continue;
      seen.add(i);
      const entry = searchEntries[i];
      if (entry && keep(entry)) entries.push(entry);
    }
  };

  collect(rankedIndexes(ufExact, hs, q));
  const exactCount = entries.length;
  if (entries.length < limit) collect(rankedIndexes(ufFuzzy, hs, q));
  return { entries, exactCount };
}
