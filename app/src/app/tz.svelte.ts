/**
 * Display-timezone preference. Purely cosmetic and per-device, so it lives
 * in localStorage rather than the notebook DO — and works offline for free.
 */
import { timeZoneAbbreviation } from "./format";

export type TimeMode = "venue" | "home";

const TIME_MODE_KEY = "conferences:time-mode";
const LEGACY_TIME_MODE_KEY = "aaic:tz";
export const HOME_TIME_ZONE = "Europe/Zurich";

function storedMode(): TimeMode {
  const current = localStorage.getItem(TIME_MODE_KEY);
  if (current === "home" || current === "venue") return current;
  const legacy = localStorage.getItem(LEGACY_TIME_MODE_KEY);
  const migrated = legacy === "zurich" ? "home" : "venue";
  if (legacy) localStorage.setItem(TIME_MODE_KEY, migrated);
  return migrated;
}

export const tz = $state<{
  mode: TimeMode;
  venueTimeZone: string;
  conferenceDate: string;
}>({
  mode: storedMode(),
  venueTimeZone: "UTC",
  conferenceDate: "1970-01-01",
});

export function setVenueTimeZone(
  timeZone: string,
  conferenceDate: string,
): void {
  tz.venueTimeZone = timeZone;
  tz.conferenceDate = conferenceDate;
}

export function selectedTimeZone(): string {
  return tz.mode === "home" ? HOME_TIME_ZONE : tz.venueTimeZone;
}

export function timeModeLabel(mode: TimeMode): string {
  const timeZone = mode === "home" ? HOME_TIME_ZONE : tz.venueTimeZone;
  // NOTE: The marker uses the conference start date. If a future conference
  // spans a DST transition, derive it from the active day or show both zones.
  return `${timeZoneAbbreviation(timeZone, tz.conferenceDate)} (${mode})`;
}

export function toggleTimeMode(): void {
  tz.mode = tz.mode === "venue" ? "home" : "venue";
  localStorage.setItem(TIME_MODE_KEY, tz.mode);
}
