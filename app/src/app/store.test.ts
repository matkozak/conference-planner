import { afterEach, expect, it, vi } from "vitest";
import type { ConferenceProgram } from "../shared/program";

vi.mock("./tz.svelte", () => ({ setVenueTimeZone: vi.fn() }));
afterEach(() => vi.unstubAllGlobals());

it("indexes continuation-only days and searches each item once using its own dates", async () => {
  // Exercise store logic in Node; this test does not exercise Svelte reactivity.
  vi.stubGlobal("$state", <T>(value: T) => value);
  vi.stubGlobal("location", { pathname: "/test/", hash: "#/day/2026-11-17" });
  vi.stubGlobal("window", { addEventListener: vi.fn() });
  vi.stubGlobal("document", { title: "" });
  const program: ConferenceProgram = {
    schema_version: 1,
    conference: {
      id: "test",
      name: "Test",
      short_name: "Test",
      starts_on: "2026-11-16",
      ends_on: "2026-11-17",
      timezone: "America/New_York",
    },
    days: ["2026-11-16"],
    people: {},
    sessions: [
      {
        id: "theme",
        title: "Innovation",
        kind: "poster-session",
        date: "2026-11-16",
        starts_at: "2026-11-16T14:00:00-05:00",
        ends_at: "2026-11-17T17:30:00-05:00",
        presentations: [
          { id: "P1", title: "Innovation poster", kind: "poster" },
          {
            id: "P2",
            title: "Innovation presentation",
            kind: "poster",
            starts_at: "2026-11-17T09:00:00-05:00",
          },
        ],
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          schema_version: 1,
          conferences: [
            { ...program.conference, program_hash: "a".repeat(64) },
          ],
        }),
      })
      .mockResolvedValueOnce({ ok: true, json: async () => program }),
  );
  const store = await import("./store.svelte");
  expect(await store.init()).toBe(true);
  expect(store.ui.route).toEqual({ view: "day", day: "2026-11-17" });
  expect([...store.sessionsByDay.keys()]).toEqual(["2026-11-16", "2026-11-17"]);
  expect(store.posterSessionsByDay.get("2026-11-17")![0]).toBe(
    program.sessions[0],
  );
  expect(
    store
      .search("Innovation", { scope: "posters", day: "2026-11-16" })
      .entries.map((e) => e.talk!.id),
  ).toEqual(["P1"]);
  expect(
    store.search("Innovation", { scope: "posters", day: "2026-11-17" }).entries,
  ).toHaveLength(2);
  expect(store.search("Innovation", { scope: "posters" }).entries).toHaveLength(
    2,
  );
  expect(program.days).toEqual(["2026-11-16"]);
});
