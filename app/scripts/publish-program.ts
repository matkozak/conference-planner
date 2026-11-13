import { readFileSync } from "node:fs";

import { publishProgram, type R2PublicationConfig } from "./publication.ts";
import { parseConferenceProgram } from "../src/shared/program.ts";
import {
  reviewArguments,
  reviewProductionCandidate,
} from "./production-access.ts";

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be set`);
  return value;
}

async function main(): Promise<void> {
  const { file, force } = reviewArguments(
    process.argv.slice(2),
    "program:publish",
  );

  const config: R2PublicationConfig = {
    accountId: requiredEnv("R2_ACCOUNT_ID"),
    accessKeyId: requiredEnv("R2_ACCESS_KEY_ID"),
    secretAccessKey: requiredEnv("R2_SECRET_ACCESS_KEY"),
    bucket: process.env.R2_BUCKET ?? "conference-programs",
  };
  const program = parseConferenceProgram(
    JSON.parse(readFileSync(file, "utf8")) as unknown,
  );
  const review = reviewProductionCandidate(program, force);
  const result = await publishProgram(
    program,
    config,
    review.expectedCurrentHash,
  );
  console.log(
    `${result.changed ? "promoted" : "unchanged"} ` +
      `${program.conference.id}@${result.hash}`,
  );
}

await main();
