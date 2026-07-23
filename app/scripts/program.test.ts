import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import type { ConferenceProgram } from "../src/shared/program.ts";
import {
  conferenceProgramJsonSchema,
  parseConferenceProgram,
  ProgramValidationError,
} from "../src/shared/program.ts";

const fixturePath = join(
  import.meta.dirname,
  "..",
  "fixtures",
  "synthetic-program.json",
);
const fixture: ConferenceProgram = JSON.parse(
  readFileSync(fixturePath, "utf8"),
);

function changed(
  mutator: (program: ConferenceProgram) => void,
): ConferenceProgram {
  const program = structuredClone(fixture);
  mutator(program);
  return program;
}

describe("ConferenceProgram v1", () => {
  it("accepts the synthetic provider-independent fixture", () => {
    expect(parseConferenceProgram(fixture)).toEqual(fixture);
  });

  it("rejects fields outside the stable contract", () => {
    const input = { ...fixture, provider_payload: { anything: true } };
    expect(() => parseConferenceProgram(input)).toThrow(/Unrecognized key/);
  });

  it("rejects duplicate item ids and dangling person references", () => {
    const input = changed((program) => {
      const poster = program.sessions[1]?.presentations[0];
      if (poster) {
        poster.id = "talk-1";
        poster.speaker_ids = ["missing-person"];
      }
    });
    expect(() => parseConferenceProgram(input)).toThrow(
      /duplicates item id[\s\S]*unknown person id/,
    );
  });

  it("does not treat Object prototype properties as people", () => {
    const input = changed((program) => {
      const talk = program.sessions[0]?.presentations[0];
      if (talk) talk.speaker_ids = ["toString"];
    });
    expect(() => parseConferenceProgram(input)).toThrow(
      /unknown person id "toString"/,
    );
  });

  it("rejects invalid ordering, dates, and item-kind relationships", () => {
    const input = changed((program) => {
      program.days.reverse();
      const talk = program.sessions[0]?.presentations[0];
      if (talk) {
        talk.kind = "poster";
        talk.starts_at = "2027-03-02T09:10:00+01:00";
      }
    });
    expect(() => parseConferenceProgram(input)).toThrow(
      /strictly sorted[\s\S]*containing session date[\s\S]*must be talk/,
    );
  });

  it("rejects unsafe formatted descriptions and unknown timezones", () => {
    const input = changed((program) => {
      program.conference.timezone = "Europe/Nowhere";
      const session = program.sessions[0];
      if (session) session.description_html = '<b class="bad">unsafe</b>';
    });
    expect(() => parseConferenceProgram(input)).toThrow(
      /recognized IANA timezone[\s\S]*allowlisted bare formatting tags/,
    );
  });

  it("returns path-aware structural errors", () => {
    const input = changed((program) => {
      program.sessions[0]!.title = "";
    });
    try {
      parseConferenceProgram(input);
      expect.unreachable("validation should fail");
    } catch (error) {
      expect(error).toBeInstanceOf(ProgramValidationError);
      expect(String(error)).toContain("$.sessions[0].title");
    }
  });
});

describe("portable JSON Schema", () => {
  it("matches the committed generated contract", () => {
    const schemaPath = join(
      import.meta.dirname,
      "..",
      "..",
      "schema",
      "conference-program-v1.schema.json",
    );
    const committed = JSON.parse(readFileSync(schemaPath, "utf8"));
    expect(committed).toEqual(conferenceProgramJsonSchema());
  });
});
