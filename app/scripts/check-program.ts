/**
 * Validates a publication candidate without publishing it.
 *
 * External producers use this to check their output against the shared
 * contract before any production access is needed.
 */
import { readFileSync } from "node:fs";

import { parseConferenceProgram } from "../src/shared/program.ts";

function main(): void {
  const file = process.argv[2];
  if (!file) {
    throw new Error("usage: pnpm run program:check <program.json>");
  }
  const program = parseConferenceProgram(
    JSON.parse(readFileSync(file, "utf8")) as unknown,
  );
  const presentations = program.sessions.reduce(
    (count, session) => count + session.presentations.length,
    0,
  );
  console.log(
    `${file} is a valid ${program.conference.id} program: ` +
      `${program.days.length} days, ${program.sessions.length} sessions, ` +
      `${presentations} presentations, ` +
      `${Object.keys(program.people).length} people`,
  );
}

main();
