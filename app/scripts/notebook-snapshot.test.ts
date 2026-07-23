import { describe, expect, it } from "vitest";

import { notebookSnapshot } from "../src/worker/snapshot";

describe("notebookSnapshot", () => {
  it("includes both kinds of user references and the program version", () => {
    const snapshot = notebookSnapshot(
      "aaic-2026",
      "abc12345",
      [
        {
          id: 1,
          item_id: "P1",
          author: "ada@example.com",
          body: "Worth revisiting",
          created_at: "2026-07-10T12:00:00Z",
          updated_at: "2026-07-10T12:00:00Z",
        },
      ],
      [
        {
          item_id: "S1",
          author: "ada@example.com",
          created_at: "2026-07-10T12:15:00Z",
        },
      ],
      "2026-07-10T12:30:00Z",
    );

    expect(snapshot).toEqual({
      conference_id: "aaic-2026",
      program_version: "abc12345",
      exported_at: "2026-07-10T12:30:00Z",
      notes: [expect.objectContaining({ item_id: "P1" })],
      rsvps: [
        {
          item_id: "S1",
          author: "ada@example.com",
          created_at: "2026-07-10T12:15:00Z",
        },
      ],
    });
  });
});
