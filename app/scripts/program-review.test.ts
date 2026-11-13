import { describe, expect, it } from "vitest";

import fixture from "../fixtures/synthetic-program.json";
import type { NotebookSnapshot } from "../src/shared/notebook.ts";
import type { ConferenceProgram } from "../src/shared/program.ts";
import { programContentHash } from "./publication.ts";
import {
  publicationBlockers,
  renderProgramReview,
  reviewProgramUpdate,
} from "./program-review.ts";

function program(): ConferenceProgram {
  return structuredClone(fixture) as ConferenceProgram;
}

function snapshot(
  baseline: ConferenceProgram,
  itemId?: string,
): NotebookSnapshot {
  return {
    conference_id: baseline.conference.id,
    program_version: programContentHash(JSON.stringify(baseline)),
    exported_at: "2027-01-01T12:00:00Z",
    notes: itemId
      ? [
          {
            id: 1,
            item_id: itemId,
            author: "ada@example.com",
            body: "Remember this",
            created_at: "2027-01-01T11:00:00Z",
            updated_at: "2027-01-01T11:00:00Z",
          },
        ]
      : [],
    rsvps: itemId ? [{ item_id: itemId, author: "ada@example.com" }] : [],
  };
}

describe("program update review", () => {
  it("has no findings for an unchanged program", () => {
    const baseline = program();
    const review = reviewProgramUpdate(
      baseline,
      structuredClone(baseline),
      snapshot(baseline),
    );

    expect(review.summary.stable_ids).toBe(4);
    expect(review.summary.modified_ids).toBe(0);
    expect(review.items_with_user_content).toEqual([]);
  });

  it("blocks likely item ID reuse only when the item has user content", () => {
    const baseline = program();
    const candidate = program();
    const session = candidate.sessions[0];
    if (!session) throw new Error("fixture session is missing");
    session.title = "Unrelated closing ceremony";
    session.speaker_ids = [];

    const unreferenced = reviewProgramUpdate(
      baseline,
      candidate,
      snapshot(baseline),
    );
    expect(unreferenced.possible_id_reuse.map((item) => item.id)).toEqual([
      "session-1",
    ]);
    expect(publicationBlockers(unreferenced)).toEqual([]);

    const referenced = reviewProgramUpdate(
      baseline,
      candidate,
      snapshot(baseline, "session-1"),
    );
    expect(publicationBlockers(referenced)).toEqual([
      "session-1: possible item ID reuse with 1 note(s), 1 RSVP(s)",
    ]);
  });

  it("reports but does not block a content change with notes or RSVPs", () => {
    const baseline = program();
    const candidate = program();
    const talk = candidate.sessions[0]?.presentations[0];
    if (!talk) throw new Error("fixture presentation is missing");
    talk.title = "A useful result, updated";

    const review = reviewProgramUpdate(
      baseline,
      candidate,
      snapshot(baseline, "talk-1"),
    );

    expect(review.modified[0]?.references).toEqual({ notes: 1, rsvps: 1 });
    expect(publicationBlockers(review)).toEqual([]);
    expect(renderProgramReview(review)).toContain(
      "Changed/removed items with user content: 1",
    );
  });

  it("blocks removal of an item with user content", () => {
    const baseline = program();
    const candidate = program();
    const session = candidate.sessions[0];
    if (!session) throw new Error("fixture session is missing");
    session.presentations = [];

    const review = reviewProgramUpdate(
      baseline,
      candidate,
      snapshot(baseline, "talk-1"),
    );

    expect(publicationBlockers(review)).toContain(
      "talk-1: removed item has 1 note(s), 1 RSVP(s)",
    );
  });

  it("requires a snapshot for the exact baseline version", () => {
    const baseline = program();
    const badSnapshot = snapshot(baseline);
    badSnapshot.program_version = "0".repeat(64);

    expect(() => reviewProgramUpdate(baseline, program(), badSnapshot)).toThrow(
      "program_version does not match the baseline",
    );
  });
});
