/**
 * Display-timezone preference. Purely cosmetic and per-device, so it lives
 * in localStorage rather than the notebook DO — and works offline for free.
 */
import type { Zone } from "./format";

const TZ_KEY = "aaic:tz";

export const tz = $state<{ zone: Zone }>({
  zone: localStorage.getItem(TZ_KEY) === "zurich" ? "zurich" : "london",
});

export function toggleZone(): void {
  tz.zone = tz.zone === "london" ? "zurich" : "london";
  localStorage.setItem(TZ_KEY, tz.zone);
}
