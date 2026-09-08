import { expect, it, vi } from "vitest";
import type { Session } from "../shared/program";

vi.mock("./notebook.svelte", () => ({
  rsvps: new Map([["P1", ["a@example.com"]]]),
}));
vi.mock("./store.svelte", () => {
  const session: Session = {
    id: "theme",
    kind: "poster-session",
    title: "Theme",
    date: "2026-11-16",
    starts_at: "2026-11-16T14:00:00-05:00",
    ends_at: "2026-11-17T17:30:00-05:00",
    presentations: [],
  };
  return {
    ui: { program: { conference: { timezone: "America/New_York" } } },
    isPosterSession: (s: Session) => s.kind === "poster-session",
    itemsById: new Map([
      ["P1", { session, talk: { id: "P1", kind: "poster", title: "Poster" } }],
    ]),
  };
});

import { planCount, planDays } from "./plans";

it("shows one RSVP on both days without counting it twice or implying a new start", () => {
  const { posters } = planDays();
  expect([...posters.keys()]).toEqual(["2026-11-16", "2026-11-17"]);
  expect(posters.get("2026-11-16")![0]!.continuing).toBe(false);
  expect(posters.get("2026-11-17")![0]!.continuing).toBe(true);
  expect(planCount(posters)).toBe(1);
  expect(planDays(() => false).posters.size).toBe(0);
});
