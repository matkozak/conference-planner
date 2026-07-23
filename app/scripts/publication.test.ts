import { afterEach, describe, expect, it, vi } from "vitest";

import fixture from "../fixtures/synthetic-program.json";
import type { ConferenceCatalog } from "../src/shared/catalog.ts";
import type { ConferenceProgram } from "../src/shared/program.ts";
import {
  catalogWithProgram,
  publishProgram,
  programContentHash,
} from "./publication.ts";

const program = fixture as ConferenceProgram;

afterEach(() => vi.restoreAllMocks());

describe("program publication", () => {
  it("uses the full content digest", () => {
    const json = JSON.stringify(program);
    expect(programContentHash(json)).toMatch(/^[a-f0-9]{64}$/);
    expect(programContentHash(json)).not.toBe(
      programContentHash(JSON.stringify({ ...program, days: ["2027-03-02"] })),
    );
  });

  it("adds and replaces one finite catalog entry", () => {
    const first = catalogWithProgram(
      { schema_version: 1, conferences: [] },
      program,
      "a".repeat(64),
    );
    expect(first.conferences).toEqual([
      { ...program.conference, program_hash: "a".repeat(64) },
    ]);
    const second = catalogWithProgram(first, program, "b".repeat(64));
    expect(second.conferences).toHaveLength(1);
    expect(second.conferences[0]?.program_hash).toBe("b".repeat(64));
  });

  it("uploads and conditionally promotes the catalog ETag", async () => {
    const currentHash = "a".repeat(64);
    const current = catalogWithProgram(
      { schema_version: 1, conferences: [] },
      program,
      currentHash,
    );
    const requests: Request[] = [];
    let promoted = current;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (request: string | URL | Request) => {
        const received =
          request instanceof Request ? request : new Request(request);
        requests.push(received.clone());
        if (requests.length === 1) {
          return Response.json(current, { headers: { ETag: '"catalog-v1"' } });
        }
        if (requests.length === 2) return new Response(null, { status: 200 });
        if (requests.length === 3) return new Response(JSON.stringify(program));
        if (requests.length === 4) {
          promoted = JSON.parse(await received.text()) as ConferenceCatalog;
          return new Response(null, { status: 200 });
        }
        if (requests.length === 5) {
          return Response.json(promoted, {
            headers: { ETag: '"catalog-v2"' },
          });
        }
        throw new Error(`unexpected request for ${received.url}`);
      },
    );

    const result = await publishProgram(program, {
      accountId: "account",
      accessKeyId: "access",
      secretAccessKey: "secret",
      bucket: "conference-programs",
    });

    expect(requests).toHaveLength(5);
    expect(requests[1]?.method).toBe("PUT");
    expect(requests[1]?.headers.get("If-None-Match")).toBe("*");
    expect(requests[3]?.method).toBe("PUT");
    expect(requests[3]?.headers.get("If-Match")).toBe('"catalog-v1"');
    expect(promoted.conferences[0]?.program_hash).toBe(result.hash);
    expect(result.changed).toBe(true);
  });

  it("verifies an unchanged object without rewriting the catalog", async () => {
    const programJson = JSON.stringify(program);
    const hash = programContentHash(programJson);
    const current = catalogWithProgram(
      { schema_version: 1, conferences: [] },
      program,
      hash,
    );
    const requests: Request[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async (request: string | URL | Request) => {
        const received =
          request instanceof Request ? request : new Request(request);
        requests.push(received.clone());
        if (requests.length === 1) {
          return Response.json(current, { headers: { ETag: '"catalog-v1"' } });
        }
        if (requests.length === 2) return new Response(programJson);
        throw new Error(`unexpected request for ${received.url}`);
      },
    );

    const result = await publishProgram(program, {
      accountId: "account",
      accessKeyId: "access",
      secretAccessKey: "secret",
      bucket: "conference-programs",
    });

    expect(result).toEqual({ hash, changed: false });
    expect(requests.map((request) => request.method)).toEqual(["GET", "GET"]);
  });
});
