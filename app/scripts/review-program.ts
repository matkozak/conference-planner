import { readFileSync } from "node:fs";

import { parseConferenceProgram } from "../src/shared/program.ts";
import {
  reviewArguments,
  reviewProductionCandidate,
} from "./production-access.ts";

const { file, force } = reviewArguments(
  process.argv.slice(2),
  "program:review",
);
const candidate = parseConferenceProgram(
  JSON.parse(readFileSync(file, "utf8")) as unknown,
);
reviewProductionCandidate(candidate, force);
