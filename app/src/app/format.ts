import type { Session } from "../shared/types";

/**
 * Times in the program are ISO strings with the venue's UTC offset, so the
 * wall-clock part of the string IS venue-local time — no Date math needed.
 */
export function hhmm(iso?: string): string {
  return iso?.slice(11, 16) ?? "";
}

export function timeRange(start?: string, end?: string): string {
  const a = hhmm(start);
  const b = hhmm(end);
  return a && b ? `${a}–${b}` : a || b;
}

/** "2026-07-12" → "Sun 12 Jul" */
export function dayLabel(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** Today as YYYY-MM-DD in the user's timezone (== venue timezone on site). */
export function localToday(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

/** Many titles repeat their category ("Plenary - Opening…"); strip the echo. */
export function displayTitle(s: Session): string {
  const prefix = `${s.category} - `;
  return s.category && s.title.startsWith(prefix)
    ? s.title.slice(prefix.length)
    : s.title;
}
