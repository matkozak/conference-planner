import { readFileSync } from "node:fs";

import { publishProgram, type R2PublicationConfig } from "./publication.ts";
import { parseConferenceProgram } from "../src/shared/program.ts";
import { reviewProductionCandidate } from "./production-access.ts";

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} must be set`);
  return value;
}

async function main(): Promise<void> {
  const { file, allowedContentChanges } = argumentsFrom(process.argv.slice(2));

  const config: R2PublicationConfig = {
    accountId: requiredEnv("R2_ACCOUNT_ID"),
    accessKeyId: requiredEnv("R2_ACCESS_KEY_ID"),
    secretAccessKey: requiredEnv("R2_SECRET_ACCESS_KEY"),
    bucket: process.env.R2_BUCKET ?? "conference-programs",
  };
  const program = parseConferenceProgram(
    JSON.parse(readFileSync(file, "utf8")) as unknown,
  );
  const review = reviewProductionCandidate(program, allowedContentChanges);
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

function argumentsFrom(args: string[]): {
  file: string;
  allowedContentChanges: Set<string>;
} {
  const file = args.shift();
  if (!file) {
    throw new Error(
      "usage: pnpm run program:publish <program.json> [--allow-content-change ITEM_ID]",
    );
  }
  const allowedContentChanges = new Set<string>();
  while (args.length > 0) {
    const option = args.shift();
    if (option !== "--allow-content-change") {
      throw new Error(`unknown argument: ${option}`);
    }
    const itemId = args.shift();
    if (!itemId) throw new Error("--allow-content-change requires an item id");
    allowedContentChanges.add(itemId);
  }
  return { file, allowedContentChanges };
}

await main();
