import { describe, expect, it } from "vitest";

import { hhmm, initials, timeRange } from "./format";

describe("hhmm", () => {
  const iso = "2026-07-10T08:00:00+01:00";

  it("shows venue wall-clock time by default", () => {
    expect(hhmm(iso)).toBe("08:00");
  });

  it("converts to Zurich time (BST+1 in July)", () => {
    expect(hhmm(iso, "zurich")).toBe("09:00");
  });

  it("handles missing input in both zones", () => {
    expect(hhmm(undefined)).toBe("");
    expect(hhmm("", "zurich")).toBe("");
  });
});

describe("timeRange", () => {
  it("passes the zone through to both ends", () => {
    expect(
      timeRange(
        "2026-07-10T08:00:00+01:00",
        "2026-07-10T17:30:00+01:00",
        "zurich",
      ),
    ).toBe("09:00–18:30");
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
