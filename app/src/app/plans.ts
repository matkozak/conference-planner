/**
 * Day-grouped RSVP plans shared by the Me and Team views, split into the
 * oral programme vs posters — mirroring the app's top-level day/Posters
 * tab split.
 */
import { rsvps } from "./notebook.svelte";
import type { SearchEntry } from "./store.svelte";
import { isPosterSession, itemsById, ui } from "./store.svelte";
import { visibleDays } from "./schedule";

export interface PlanItem {
  entry: SearchEntry;
  startsAt: string;
  authors: string[];
  continuing: boolean;
}

export interface PlanDays {
  talks: Map<string, PlanItem[]>;
  posters: Map<string, PlanItem[]>;
}

/**
 * Group RSVPs by day, talks and posters separately, in time order.
 * `filter` narrows by RSVP authors (e.g. just the current user).
 */
export function planDays(filter?: (authors: string[]) => boolean): PlanDays {
  const talks = new Map<string, PlanItem[]>();
  const posters = new Map<string, PlanItem[]>();
  for (const [itemId, authors] of rsvps) {
    if (filter && !filter(authors)) continue;
    const entry = itemsById.get(itemId);
    if (!entry) continue;
    const startsAt = entry.talk?.starts_at ?? entry.session.starts_at ?? "";
    const byDay = isPosterSession(entry.session) ? posters : talks;
    const days = visibleDays(
      entry.session,
      ui.program!.conference.timezone,
      entry.talk,
    );
    for (const day of days) {
      const list = byDay.get(day) ?? [];
      list.push({ entry, startsAt, authors, continuing: day !== days[0] });
      byDay.set(day, list);
    }
  }
  for (const byDay of [talks, posters]) {
    for (const list of byDay.values()) {
      list.sort((a, b) => a.startsAt.localeCompare(b.startsAt));
    }
  }
  return { talks: sortDays(talks), posters: sortDays(posters) };
}

/** Unique items across all days of one plan map (for tab counts). */
export function planCount(days: Map<string, PlanItem[]>): number {
  const ids = new Set<string>();
  for (const list of days.values()) {
    for (const { entry } of list) ids.add(entry.talk?.id ?? entry.session.id);
  }
  return ids.size;
}

function sortDays(days: Map<string, PlanItem[]>): Map<string, PlanItem[]> {
  return new Map([...days].sort(([a], [b]) => a.localeCompare(b)));
}
