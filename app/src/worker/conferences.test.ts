import { describe, expect, it } from "vitest";

import { runtimeConference } from "./conferences";

describe("runtime conference resolution", () => {
  it("keeps AAIC on its legacy notebook until the verified migration", () => {
    expect(runtimeConference("aaic-2026")?.notebook_name).toBe("team");
  });

  it("does not resolve arbitrary Durable Object names", () => {
    expect(runtimeConference("made-up")).toBeUndefined();
  });
});
