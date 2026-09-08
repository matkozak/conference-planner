import { describe, expect, it } from "vitest";
import type { Presentation, Session } from "../shared/program";
import { visibleDays } from "./schedule";

const zone = "America/New_York";
const session: Session = {
  id: "theme-ai",
  kind: "poster-session",
  title: "AI",
  date: "2026-11-16",
  starts_at: "2026-11-16T14:00:00-05:00",
  ends_at: "2026-11-17T17:30:00-05:00",
  presentations: [],
};
const poster: Presentation = { id: "P1", kind: "poster", title: "Poster" };

describe("visibleDays", () => {
  it("includes both days for themes and their untimed posters", () => {
    expect(visibleDays(session, zone)).toEqual(["2026-11-16", "2026-11-17"]);
    expect(visibleDays(session, zone, poster)).toEqual([
      "2026-11-16",
      "2026-11-17",
    ]);
  });

  it("uses a presentation's own timing, including a start without an end", () => {
    expect(
      visibleDays(session, zone, {
        ...poster,
        starts_at: "2026-11-17T09:00:00-05:00",
      }),
    ).toEqual(["2026-11-17"]);
    expect(
      visibleDays(session, zone, {
        ...poster,
        starts_at: session.starts_at,
        ends_at: "2026-11-16T15:00:00-05:00",
      }),
    ).toEqual(["2026-11-16"]);
  });

  it("excludes midnight in the venue zone, even with UTC source timestamps", () => {
    expect(
      visibleDays({ ...session, ends_at: "2026-11-17T05:00:00Z" }, zone),
    ).toEqual(["2026-11-16"]);
    expect(
      visibleDays({ ...session, ends_at: "2026-11-17T05:00:00.001Z" }, zone),
    ).toEqual(["2026-11-16", "2026-11-17"]);
  });

  it("falls back to the canonical day for an unknown schedule", () => {
    expect(
      visibleDays(
        { ...session, starts_at: undefined, ends_at: undefined },
        zone,
      ),
    ).toEqual(["2026-11-16"]);
  });

  it("includes intermediate dates across a DST change", () => {
    expect(
      visibleDays(
        {
          ...session,
          date: "2026-10-31",
          starts_at: "2026-10-31T14:00:00-04:00",
          ends_at: "2026-11-02T10:00:00-05:00",
        },
        zone,
      ),
    ).toEqual(["2026-10-31", "2026-11-01", "2026-11-02"]);
  });
});
