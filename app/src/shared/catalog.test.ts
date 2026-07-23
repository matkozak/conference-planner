import { describe, expect, it } from "vitest";

import {
  CONFERENCE_CATALOG,
  conferenceForLocation,
  conferenceStatus,
} from "./catalog";

const aaic = CONFERENCE_CATALOG[0]!;

describe("conference catalog routing", () => {
  it("resolves only finite top-level conference slugs", () => {
    expect(conferenceForLocation("/aaic-2026/", "conferences.kozak.ch")).toBe(
      aaic,
    );
    expect(
      conferenceForLocation("/made-up/", "conferences.kozak.ch"),
    ).toBeUndefined();
    expect(
      conferenceForLocation("/aaic-2026/extra", "conferences.kozak.ch"),
    ).toBeUndefined();
  });

  it("keeps the historical AAIC hostname rooted at AAIC", () => {
    expect(conferenceForLocation("/", "aaic2026.kozak.ch")).toBe(aaic);
    expect(conferenceForLocation("/", "conferences.kozak.ch")).toBeNull();
  });
});

describe("conference status", () => {
  it("classifies dates against the conference range", () => {
    expect(conferenceStatus(aaic, "2026-07-09")).toBe("upcoming");
    expect(conferenceStatus(aaic, "2026-07-12")).toBe("current");
    expect(conferenceStatus(aaic, "2026-07-17")).toBe("past");
  });
});
