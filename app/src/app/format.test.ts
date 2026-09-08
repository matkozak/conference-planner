import { describe, expect, it } from "vitest";

import {
  dayLabel,
  dayTab,
  hhmm,
  initials,
  noteStamp,
  timeZoneAbbreviation,
  timeRange,
  todayInTimeZone,
} from "./format";

describe("hhmm", () => {
  const iso = "2026-07-10T08:00:00+01:00";

  it("formats in the venue timezone", () => {
    expect(hhmm(iso, "Europe/London")).toBe("08:00");
  });

  it("formats in the home timezone", () => {
    expect(hhmm(iso, "Europe/Zurich")).toBe("09:00");
  });

  it("handles missing input in both zones", () => {
    expect(hhmm(undefined, "Europe/London")).toBe("");
    expect(hhmm("", "Europe/Zurich")).toBe("");
  });
});

describe("timeRange", () => {
  it("can include the day for a same-day detail heading", () => {
    expect(
      timeRange(
        "2026-11-16T14:00:00-05:00",
        "2026-11-16T17:30:00-05:00",
        "America/New_York",
        true,
      ),
    ).toBe("Mon 16 Nov, 14:00–17:30");
  });
  it("passes the zone through to both ends", () => {
    expect(
      timeRange(
        "2026-07-10T08:00:00+01:00",
        "2026-07-10T17:30:00+01:00",
        "Europe/Zurich",
      ),
    ).toBe("09:00–18:30");
  });

  it("labels both days of a cross-day range", () => {
    expect(
      timeRange(
        "2026-11-16T14:00:00-05:00",
        "2026-11-17T17:30:00-05:00",
        "America/New_York",
      ),
    ).toBe("Mon 16 Nov, 14:00\u2009–\u2009Tue 17 Nov, 17:30");
  });
});

describe("calendar formatting", () => {
  it("finds today in the venue timezone", () => {
    const instant = new Date("2026-11-10T23:30:00Z");
    expect(todayInTimeZone("America/New_York", instant)).toBe("2026-11-10");
    expect(todayInTimeZone("Europe/Zurich", instant)).toBe("2026-11-11");
  });

  it("formats conference dates independently of the device timezone", () => {
    expect(dayLabel("2026-07-12")).toBe("Sun 12 Jul");
    expect(dayTab("2026-07-12")).toBe("Sun 12");
  });

  it("formats note timestamps in an explicit timezone", () => {
    expect(noteStamp("2026-07-10T07:00:00Z", "Europe/Zurich")).toBe(
      "10 Jul 09:00",
    );
  });

  it("labels zones using the conference date's daylight-saving rules", () => {
    expect(timeZoneAbbreviation("Europe/London", "2026-07-10")).toBe("BST");
    expect(timeZoneAbbreviation("Europe/London", "2026-11-10")).toBe("GMT");
    expect(timeZoneAbbreviation("Europe/Zurich", "2026-07-10")).toBe("CEST");
  });
});

describe("initials", () => {
  it("uses first letters of dotted local parts", () => {
    expect(initials("mateusz.kozak@example.com")).toBe("MK");
  });

  it("handles hyphens and underscores", () => {
    expect(initials("anna-maria_x@example.com")).toBe("AM");
  });

  it("falls back to two letters for single-word locals", () => {
    expect(initials("bob@example.com")).toBe("BO");
  });

  it("survives degenerate input", () => {
    expect(initials("anonymous")).toBe("AN");
    expect(initials("")).toBe("");
  });
});
