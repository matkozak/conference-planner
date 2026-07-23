import { describe, expect, it } from "vitest";

import {
  AAIC_NOTEBOOK_MIGRATION,
  isAaicMigrationConfirmation,
  notebookRowsEqual,
  type NotebookRows,
} from "./notebook-migration";

const rows: NotebookRows = {
  notes: [
    {
      id: 1,
      item_id: "P1",
      author: "ada@example.com",
      body: "Important",
      created_at: "2026-07-10T12:00:00Z",
      updated_at: "2026-07-10T12:00:00Z",
    },
  ],
  rsvps: [
    {
      item_id: "S1",
      author: "ada@example.com",
      created_at: "2026-07-10T11:00:00Z",
    },
  ],
};

describe("AAIC notebook migration guards", () => {
  it("requires every exact hardcoded confirmation field", () => {
    expect(isAaicMigrationConfirmation(AAIC_NOTEBOOK_MIGRATION)).toBe(true);
    expect(
      isAaicMigrationConfirmation({
        ...AAIC_NOTEBOOK_MIGRATION,
        destination: "made-up",
      }),
    ).toBe(false);
    expect(
      isAaicMigrationConfirmation({
        conference_id: "aaic-2026",
      }),
    ).toBe(false);
  });

  it("compares all persisted notebook fields in stable order", () => {
    expect(notebookRowsEqual(rows, structuredClone(rows))).toBe(true);
    const changed = structuredClone(rows);
    changed.rsvps[0]!.created_at = "2026-07-10T11:01:00Z";
    expect(notebookRowsEqual(rows, changed)).toBe(false);
  });
});
