import { spawnSync } from "node:child_process";

import {
  conferenceById,
  parseConferenceCatalog,
  programPath,
} from "../src/shared/catalog.ts";
import {
  parseConferenceProgram,
  type ConferenceProgram,
} from "../src/shared/program.ts";
import { programContentHash } from "./publication.ts";
import {
  publicationBlockers,
  renderProgramReview,
  reviewProgramUpdate,
} from "./program-review.ts";

const DEFAULT_PRODUCTION_URL = "https://conferences.kozak.ch";

export interface ProductionReviewResult {
  expectedCurrentHash: string | null;
  candidateHash: string;
  changed: boolean;
}

/** Parse `<program.json> [--force]` for the review and publish commands. */
export function reviewArguments(
  args: string[],
  command: string,
): { file: string; force: boolean } {
  const [file, ...options] = args;
  if (!file || file.startsWith("--")) {
    throw new Error(`usage: pnpm run ${command} <program.json> [--force]`);
  }
  const unknown = options.find((option) => option !== "--force");
  if (unknown !== undefined) throw new Error(`unknown argument: ${unknown}`);
  return { file, force: options.includes("--force") };
}

/**
 * Fetch production through Access and review the candidate against it.
 *
 * Blockers stop the update unless `force` acknowledges the printed review.
 */
export function reviewProductionCandidate(
  candidate: ConferenceProgram,
  force: boolean,
): ProductionReviewResult {
  const candidateHash = programContentHash(JSON.stringify(candidate));
  const catalog = parseConferenceCatalog(accessJson("/api/catalog"));
  const current = conferenceById(catalog, candidate.conference.id);
  if (!current) {
    console.log(
      `${candidate.conference.id} is not published yet; no existing identity to review.`,
    );
    return { expectedCurrentHash: null, candidateHash, changed: true };
  }
  if (current.program_hash === candidateHash) {
    console.log(
      `${candidate.conference.id}@${candidateHash} is already current.`,
    );
    return {
      expectedCurrentHash: current.program_hash,
      candidateHash,
      changed: false,
    };
  }

  const baseline = parseConferenceProgram(accessJson(programPath(current)));
  const snapshot = accessJson(
    `/api/conferences/${encodeURIComponent(candidate.conference.id)}/notebook/export.json`,
  );
  const review = reviewProgramUpdate(baseline, candidate, snapshot);
  process.stdout.write(renderProgramReview(review));
  const blockers = publicationBlockers(review);
  if (blockers.length > 0) {
    const list = blockers.map((blocker) => `- ${blocker}`).join("\n");
    if (!force) {
      throw new Error(`Publication blocked (pass --force to accept):\n${list}`);
    }
    console.log(`\nAccepted with --force:\n${list}`);
  }
  return {
    expectedCurrentHash: current.program_hash,
    candidateHash,
    changed: true,
  };
}

function accessJson(path: string): unknown {
  const text = accessText(path);
  try {
    return JSON.parse(text) as unknown;
  } catch (error) {
    throw new Error(`production returned invalid JSON for ${path}`, {
      cause: error,
    });
  }
}

function accessText(path: string): string {
  const base = (
    process.env.CONFERENCE_APP_URL ?? DEFAULT_PRODUCTION_URL
  ).replace(/\/+$/, "");
  const result = spawnSync(
    "mise",
    [
      "exec",
      "--",
      "cloudflared",
      "access",
      "curl",
      `${base}${path}`,
      "--fail",
      "--silent",
      "--show-error",
    ],
    { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"] },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`could not fetch ${path} through Cloudflare Access`);
  }
  return result.stdout;
}
