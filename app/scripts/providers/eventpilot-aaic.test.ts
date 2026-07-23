import { describe, expect, it } from "vitest";

import {
  adaptAaicProgram,
  sanitizeHtml,
  trimPerson,
  trimPresentation,
  trimSession,
} from "./eventpilot-aaic.ts";

const rawTalk = {
  id: "P1",
  title: "A talk",
  starts_at: "2026-07-12T09:00:00+01:00",
  ends_at: "",
  location: "Hall 1",
  speaker_ids: [],
  description_text: "Someone; Somewhere",
  // Relational and parent fields must not survive the adapter.
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
  it("keeps only contract fields and drops empties", () => {
    expect(trimPresentation(rawTalk)).toEqual({
      kind: "talk",
      id: "P1",
      title: "A talk",
      starts_at: "2026-07-12T09:00:00+01:00",
      location: "Hall 1",
      description_html: "Someone; Somewhere",
    });
  });
});

describe("trimSession", () => {
  it("embeds trimmed presentations and drops relational hints", () => {
    const session = trimSession(rawSession);
    expect(session.kind).toBe("session");
    expect(session.date).toBe("2026-07-12");
    expect(session.presentations).toHaveLength(1);
    expect(session).not.toHaveProperty("subsession_ids");
    expect(session.presentations[0]).not.toHaveProperty("parent_id");
  });

  it("normalizes EventPilot poster categories into explicit item kinds", () => {
    const session = trimSession({ ...rawSession, category: "Poster" });
    expect(session.kind).toBe("poster-session");
    expect(session.presentations[0]?.kind).toBe("poster");
  });

  it("rejects sessions without a date", () => {
    expect(() => trimSession({ id: "S2", title: "No date" })).toThrow(
      /no date/,
    );
  });
});

describe("sanitizeHtml", () => {
  it("keeps allowlisted bare tags and strips everything else", () => {
    expect(
      sanitizeHtml(
        '<b>Jane Doe</b><sup>1</sup>, John Roe<sup>2</sup>; <br/><script>alert(1)</script><a href="x" onclick="evil()">link</a>',
      ),
    ).toBe(
      "<b>Jane Doe</b><sup>1</sup>, John Roe<sup>2</sup>; <br>alert(1)link",
    );
  });

  it("strips attributes from allowed tags and drops comments", () => {
    expect(
      sanitizeHtml(
        '<B class="x">hi</B><!-- sneaky --><img src=x onerror=evil()>',
      ),
    ).toBe("<b>hi</b>");
  });
});

describe("presentation ordering", () => {
  it("sorts by starts_at with missing times last", () => {
    const session = trimSession({
      id: "S9",
      title: "Rotated",
      date: "2026-07-12",
      presentations: [
        {
          id: "P3",
          title: "last talk",
          starts_at: "2026-07-12T08:26:00+01:00",
        },
        {
          id: "P1",
          title: "first talk",
          starts_at: "2026-07-12T08:02:00+01:00",
        },
        { id: "P4", title: "no time" },
        {
          id: "P2",
          title: "middle talk",
          starts_at: "2026-07-12T08:10:00+01:00",
        },
      ],
    });
    expect(
      session.presentations.map((presentation) => presentation.id),
    ).toEqual(["P1", "P2", "P3", "P4"]);
  });
});

describe("trimPerson", () => {
  it("prefers full_name and falls back to name parts", () => {
    expect(
      trimPerson({
        full_name: "Ada Lovelace",
        organization: "Analytical Engines",
      }),
    ).toEqual({ name: "Ada Lovelace", org: "Analytical Engines" });
    expect(
      trimPerson({
        first_name: "Ada",
        last_name: "Lovelace",
        organization: "",
      }),
    ).toEqual({ name: "Ada Lovelace" });
  });
});

describe("adaptAaicProgram", () => {
  it("adds conference metadata and returns a validated contract", () => {
    const program = adaptAaicProgram([rawSession], {
      "42": { full_name: "Ada Lovelace" },
    });
    expect(program.schema_version).toBe(1);
    expect(program.conference).toEqual({
      id: "aaic-2026",
      name: "Alzheimer's Association International Conference 2026",
      short_name: "AAIC 2026",
      starts_on: "2026-07-12",
      ends_on: "2026-07-12",
      timezone: "Europe/London",
    });
  });
});
