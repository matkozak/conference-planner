import { describe, expect, it } from "vitest";

import {
  buildProgram,
  trimPerson,
  trimPresentation,
  trimSession,
} from "./build-program.ts";

const rawTalk = {
  id: "P1",
  title: "A talk",
  starts_at: "2026-07-12T09:00:00+01:00",
  ends_at: "",
  location: "Hall 1",
  speaker_ids: [],
  description_text: "Someone; Somewhere",
  // relational hints that must NOT survive the trim
  parent_id: "S1",
  category: "Ignored on presentations",
};

const rawSession = {
  id: "S1",
  title: "A session",
  date: "2026-07-12",
  category: "Plenary",
  session_number: "1-01",
  speaker_ids: ["42"],
  subsession_ids: ["P1"],
  presentations: [rawTalk],
};

describe("trimPresentation", () => {
  it("keeps only the app-facing fields and drops empties", () => {
    expect(trimPresentation(rawTalk)).toEqual({
      id: "P1",
      title: "A talk",
      starts_at: "2026-07-12T09:00:00+01:00",
      location: "Hall 1",
      description: "Someone; Somewhere",
    });
  });
});

describe("trimSession", () => {
  it("embeds trimmed presentations and drops relational hints", () => {
    const s = trimSession(rawSession);
    expect(s.date).toBe("2026-07-12");
    expect(s.presentations).toHaveLength(1);
    expect(s).not.toHaveProperty("subsession_ids");
    expect(s.presentations[0]).not.toHaveProperty("parent_id");
  });

  it("rejects sessions without a date", () => {
    expect(() => trimSession({ id: "S2", title: "No date" })).toThrow(
      /no date/,
    );
  });
});

describe("trimPerson", () => {
  it("prefers full_name and falls back to parts", () => {
    expect(
      trimPerson({
        full_name: "Ada Lovelace",
        organization: "Analytical Engines",
      }),
    ).toEqual({
      name: "Ada Lovelace",
      org: "Analytical Engines",
    });
    expect(
      trimPerson({
        first_name: "Ada",
        last_name: "Lovelace",
        organization: "",
      }),
    ).toEqual({
      name: "Ada Lovelace",
    });
  });
});

describe("buildProgram", () => {
  it("derives sorted unique days and a stable content hash", () => {
    const a = buildProgram([rawSession], {
      "42": { full_name: "Ada Lovelace" },
    });
    const b = buildProgram([rawSession], {
      "42": { full_name: "Ada Lovelace" },
    });
    expect(a.days).toEqual(["2026-07-12"]);
    expect(a.version).toBe(b.version);
    expect(a.version).toMatch(/^[0-9a-f]{8}$/);
  });

  it("changes the hash when content changes", () => {
    const a = buildProgram([rawSession], {});
    const b = buildProgram([{ ...rawSession, title: "Renamed" }], {});
    expect(a.version).not.toBe(b.version);
  });
});
