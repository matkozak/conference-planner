import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { programContentHash } from "./build-program.ts";
import {
  adaptAaicProgram,
  type RawEventPilotItem,
  type RawEventPilotPerson,
} from "./providers/eventpilot-aaic.ts";

const DATA_DIR = join(import.meta.dirname, "..", "..", "data", "aaic_2026");

describe("current AAIC program", () => {
  const rawSessions: RawEventPilotItem[] = JSON.parse(
    readFileSync(join(DATA_DIR, "sessions.json"), "utf8"),
  );
  const rawPeople: Record<string, RawEventPilotPerson> = JSON.parse(
    readFileSync(join(DATA_DIR, "people.json"), "utf8"),
  );
  const program = adaptAaicProgram(rawSessions, rawPeople);

  it("conforms to ConferenceProgram v1", () => {
    expect(program.conference.id).toBe("aaic-2026");
    expect(program.sessions).toHaveLength(rawSessions.length);
    expect(program.days).toEqual([
      "2026-07-10",
      "2026-07-11",
      "2026-07-12",
      "2026-07-13",
      "2026-07-14",
      "2026-07-15",
      "2026-07-16",
    ]);
  });

  it("has a stable content hash outside the contract", () => {
    expect(program).not.toHaveProperty("version");
    const hash = programContentHash(program);
    const changed = structuredClone(program);
    changed.sessions[0]!.title += " (changed)";
    expect(hash).toMatch(/^[0-9a-f]{8}$/);
    expect(programContentHash(structuredClone(program))).toBe(hash);
    expect(programContentHash(changed)).not.toBe(hash);
  });
});
