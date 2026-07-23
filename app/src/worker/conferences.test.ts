import { describe, expect, it } from "vitest";

import { runtimeConference } from "./conferences";

describe("runtime conference resolution", () => {
  it("uses the conference id as its notebook name", () => {
    expect(runtimeConference("aaic-2026")?.notebook_name).toBe("aaic-2026");
  });

  it("does not resolve arbitrary Durable Object names", () => {
    expect(runtimeConference("made-up")).toBeUndefined();
  });
});
