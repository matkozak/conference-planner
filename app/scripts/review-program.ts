import { readFileSync } from "node:fs";

import { parseConferenceProgram } from "../src/shared/program.ts";
import { reviewProductionCandidate } from "./production-access.ts";

const { file, allowedContentChanges } = argumentsFrom(process.argv.slice(2));
const candidate = parseConferenceProgram(
  JSON.parse(readFileSync(file, "utf8")) as unknown,
);
reviewProductionCandidate(candidate, allowedContentChanges);

function argumentsFrom(args: string[]): {
  file: string;
  allowedContentChanges: Set<string>;
} {
  const file = args.shift();
  if (!file) {
    throw new Error(
      "usage: pnpm run program:review <program.json> [--allow-content-change ITEM_ID]",
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
