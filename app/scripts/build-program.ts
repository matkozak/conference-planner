/**
 * Builds the current AAIC scrape into a validated publication candidate.
 *
 * This producer is deliberately separate from both the app build and the
 * generic R2 publisher. Its default output is ignored by Git.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

import type { ConferenceProgram } from "../src/shared/program.ts";
import {
  conferenceProgramJsonSchema,
  parseConferenceProgram,
} from "../src/shared/program.ts";
import {
  adaptAaicProgram,
  type RawEventPilotItem,
  type RawEventPilotPerson,
} from "./providers/eventpilot-aaic.ts";

const APP_ROOT = join(import.meta.dirname, "..");
const REPOSITORY_ROOT = join(APP_ROOT, "..");
const DATA_DIR = join(REPOSITORY_ROOT, "data", "aaic_2026");

export function buildAaicProgram(): ConferenceProgram {
  const rawSessions: RawEventPilotItem[] = JSON.parse(
    readFileSync(join(DATA_DIR, "sessions.json"), "utf8"),
  );
  const rawPeople: Record<string, RawEventPilotPerson> = JSON.parse(
    readFileSync(join(DATA_DIR, "people.json"), "utf8"),
  );
  return parseConferenceProgram(adaptAaicProgram(rawSessions, rawPeople));
}

function main(): void {
  const output = resolve(
    process.argv[2] ?? join(APP_ROOT, ".programs", "aaic-2026.json"),
  );
  const program = buildAaicProgram();
  const json = JSON.stringify(program);
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, json);

  const schemaDir = join(REPOSITORY_ROOT, "schema");
  mkdirSync(schemaDir, { recursive: true });
  writeFileSync(
    join(schemaDir, "conference-program-v1.schema.json"),
    `${JSON.stringify(conferenceProgramJsonSchema(), null, 2)}\n`,
  );

  const presentations = program.sessions.reduce(
    (count, session) => count + session.presentations.length,
    0,
  );
  console.log(
    `wrote ${output}: ${program.days.length} days, ` +
      `${program.sessions.length} sessions, ${presentations} presentations, ` +
      `${Object.keys(program.people).length} people`,
  );
}

if (process.argv[1] === import.meta.filename) main();
