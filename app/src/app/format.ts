import type { Session } from "../shared/program";

/** Display timezone: venue time (London) or home time (Zurich). */
export type Zone = "london" | "zurich";

/** The conference runs in July 2026, so both zones are firmly in DST. */
export const ZONE_LABEL: Record<Zone, string> = {
  london: "BST",
  zurich: "CEST",
};

const zurichTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/Zurich",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/**
 * Times in the program are ISO strings with the venue's UTC offset, so the
 * wall-clock part of the string IS venue-local time — no Date math needed
 * unless the user asked for Zurich time. (No session ends past mid-afternoon
 * venue time, so the +1h shift can never move an item to another day.)
 */
export function hhmm(iso?: string, zone: Zone = "london"): string {
  if (!iso) return "";
  return zone === "london"
    ? iso.slice(11, 16)
    : zurichTime.format(new Date(iso));
}

export function timeRange(
  start?: string,
  end?: string,
  zone: Zone = "london",
): string {
  const a = hhmm(start, zone);
  const b = hhmm(end, zone);
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

/** "2026-07-12" → "Sun 12" (compact form for the tab bar). */
export function dayTab(date: string): string {
  return new Date(`${date}T12:00:00`).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
  });
}

/** Note timestamp: "2026-07-08T13:32:05Z" → "8 Jul 14:32" (local time). */
export function noteStamp(iso: string, withTime = true): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString("en-GB", {
    month: "short",
    day: "numeric",
  });
  if (!withTime) return date;
  const time = d.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${date} ${time}`;
}

/** "Board no. Sunday-0149" → "Sunday-0149"; other locations unchanged. */
export function boardNo(location?: string): string {
  return location?.startsWith("Board no. ")
    ? location.slice("Board no. ".length)
    : (location ?? "");
}

/**
 * Poster session titles carry a redundant "[In-Person Posters Sun]" style
 * prefix; the Posters tab already groups by day, so strip it there.
 */
export function posterTopic(s: Session): string {
  return displayTitle(s).replace(/^\[[^\]]*\]\s*/, "");
}

/** "mateusz.kozak@x.com" → "MK"; single-word local parts use two letters. */
export function initials(email: string): string {
  const local = email.split("@")[0] ?? email;
  const parts = local.split(/[._-]+/).filter(Boolean);
  const two = (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "");
  return (parts.length >= 2 ? two : local.slice(0, 2)).toUpperCase();
}

/** Many titles repeat their category ("Plenary - Opening…"); strip the echo. */
export function displayTitle(s: Session): string {
  const prefix = `${s.category} - `;
  return s.category && s.title.startsWith(prefix)
    ? s.title.slice(prefix.length)
    : s.title;
}
