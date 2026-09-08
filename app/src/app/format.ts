const timeFormatters = new Map<string, Intl.DateTimeFormat>();

function timeFormatter(timeZone: string): Intl.DateTimeFormat {
  let formatter = timeFormatters.get(timeZone);
  if (!formatter) {
    formatter = new Intl.DateTimeFormat("en-GB", {
      timeZone,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    });
    timeFormatters.set(timeZone, formatter);
  }
  return formatter;
}

/** Short zone name (BST, CET, …) for a representative calendar date. */
export function timeZoneAbbreviation(timeZone: string, date: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    timeZoneName: "short",
  }).formatToParts(new Date(`${date}T12:00:00Z`));
  return parts.find((part) => part.type === "timeZoneName")?.value ?? timeZone;
}

/** Format a program timestamp in an explicit IANA timezone. */
export function hhmm(iso: string | undefined, timeZone: string): string {
  if (!iso) return "";
  return timeFormatter(timeZone).format(new Date(iso));
}

export function timeRange(
  start: string | undefined,
  end: string | undefined,
  timeZone: string,
  includeDay = false,
): string {
  const a = hhmm(start, timeZone);
  const b = hhmm(end, timeZone);
  if (!start || !end) return a || b;

  const startDay = zonedDay(start, timeZone);
  const endDay = zonedDay(end, timeZone);
  return startDay === endDay
    ? `${includeDay ? `${startDay}, ` : ""}${a}–${b}`
    : `${startDay}, ${a}\u2009–\u2009${endDay}, ${b}`;
}

/** An instant's compact calendar day in an explicit timezone. */
function zonedDay(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date(iso));
}

/** "2026-07-12" → "Sun 12 Jul" */
export function dayLabel(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

/** Today as YYYY-MM-DD in an explicit IANA timezone. */
export function todayInTimeZone(timeZone: string, now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((candidate) => candidate.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

/** "2026-07-12" → "Sun 12" (compact form for the tab bar). */
export function dayTab(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", {
    timeZone: "UTC",
    weekday: "short",
    day: "numeric",
  });
}

/** Note timestamp in the selected venue/home timezone. */
export function noteStamp(
  iso: string,
  timeZone: string,
  withTime = true,
): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString("en-GB", {
    timeZone,
    month: "short",
    day: "numeric",
  });
  if (!withTime) return date;
  const time = d.toLocaleTimeString("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  return `${date} ${time}`;
}

/** "mateusz.kozak@x.com" → "MK"; single-word local parts use two letters. */
export function initials(email: string): string {
  const local = email.split("@")[0] ?? email;
  const parts = local.split(/[._-]+/).filter(Boolean);
  const two = (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "");
  return (parts.length >= 2 ? two : local.slice(0, 2)).toUpperCase();
}
