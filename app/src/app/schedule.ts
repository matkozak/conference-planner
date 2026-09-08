import type { Presentation, Session } from "../shared/program";
import { todayInTimeZone } from "./format";

/** Conference-local days occupied by an item; an end at midnight is exclusive. */
export function visibleDays(
  session: Session,
  timeZone: string,
  presentation?: Presentation,
): string[] {
  const item = presentation ?? session;
  const start = item.starts_at ?? session.starts_at;
  const end = item.ends_at ?? (item.starts_at ? undefined : session.ends_at);
  const first = start
    ? todayInTimeZone(timeZone, new Date(start))
    : session.date;
  if (!end) return [first];
  const last = todayInTimeZone(timeZone, new Date(Date.parse(end) - 1));
  const days = [first];
  // Increment calendar dates in UTC, not instants in the venue's DST timezone.
  for (let day = first; day < last;) {
    const next = new Date(`${day}T00:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    day = next.toISOString().slice(0, 10);
    days.push(day);
  }
  return days;
}
