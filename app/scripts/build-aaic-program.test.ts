import { existsSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { AAIC_DATA_DIR, buildAaicProgram } from "./build-aaic-program.ts";

describe("current AAIC program", () => {
  const hasLocalData = ["sessions.json", "people.json"].every((name) =>
    existsSync(join(AAIC_DATA_DIR, name)),
  );

  it.skipIf(!hasLocalData)("conforms to ConferenceProgram v1", () => {
    const program = buildAaicProgram();
    expect(program.conference.id).toBe("aaic-2026");
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
});
