import { describe, expect, it } from "vitest";

import { initials } from "./format";

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
