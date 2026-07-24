import { describe, expect, it } from "vitest";

import {
  conferenceForLocation,
  conferenceStatus,
  parseConferenceCatalog,
  programKey,
  programPath,
  type ConferenceCatalog,
} from "./catalog";

const hash = "a".repeat(64);
const catalog: ConferenceCatalog = {
  schema_version: 1,
  conferences: [
    {
      id: "aaic-2026",
      name: "Alzheimer's Association International Conference 2026",
      short_name: "AAIC 2026",
      starts_on: "2026-07-10",
      ends_on: "2026-07-16",
      timezone: "Europe/London",
      program_hash: hash,
    },
  ],
};
const aaic = catalog.conferences[0]!;

describe("conference catalog", () => {
  it("parses a valid finite catalog", () => {
    expect(parseConferenceCatalog(catalog)).toEqual(catalog);
  });

  it("rejects duplicate ids and malformed hashes", () => {
    expect(() =>
      parseConferenceCatalog({
        ...catalog,
        conferences: [aaic, aaic],
      }),
    ).toThrow("duplicates aaic-2026");
    expect(() =>
      parseConferenceCatalog({
        ...catalog,
        conferences: [{ ...aaic, program_hash: "short" }],
      }),
    ).toThrow("program_hash is invalid");
  });

  it("derives matching R2 and authenticated API paths", () => {
    expect(programKey(aaic.id, hash)).toBe(`programs/aaic-2026/${hash}.json`);
    expect(programPath(aaic)).toBe(`/api/programs/aaic-2026/${hash}.json`);
  });
});

describe("conference catalog routing", () => {
  it("resolves only finite top-level conference slugs", () => {
    expect(conferenceForLocation(catalog, "/aaic-2026/")).toBe(aaic);
    expect(conferenceForLocation(catalog, "/made-up/")).toBeUndefined();
    expect(conferenceForLocation(catalog, "/aaic-2026/extra")).toBeUndefined();
  });

  it("uses the root path for the conference catalog", () => {
    expect(conferenceForLocation(catalog, "/")).toBeNull();
  });
});

describe("conference status", () => {
  it("classifies dates against the conference range", () => {
    expect(conferenceStatus(aaic, "2026-07-09")).toBe("upcoming");
    expect(conferenceStatus(aaic, "2026-07-12")).toBe("current");
    expect(conferenceStatus(aaic, "2026-07-17")).toBe("past");
  });
});
