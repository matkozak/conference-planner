import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  conferenceById,
  parseConferenceCatalog,
  programPath,
} from "../src/shared/catalog.ts";
import { parseConferenceProgram } from "../src/shared/program.ts";
import { programContentHash } from "./publication.ts";

const APP_ROOT = fileURLToPath(new URL("..", import.meta.url));
const REPOSITORY_ROOT = fileURLToPath(new URL("../..", import.meta.url));
const CANDIDATE = join(APP_ROOT, ".programs", "ctad-2026.json");
const DEFAULT_PRODUCTION_URL = "https://conferences.kozak.ch";

function run(command: string, args: string[], cwd = REPOSITORY_ROOT): void {
  const result = spawnSync(command, args, { cwd, stdio: "inherit" });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(
      `${command} ${args.join(" ")} failed with exit ${result.status}`,
    );
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
    {
      cwd: REPOSITORY_ROOT,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "inherit"],
    },
  );
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`could not fetch ${path} through Cloudflare Access`);
  }
  return result.stdout;
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

function build(): void {
  console.log("\n== Build CTAD candidate ==");
  run("python3", ["-m", "scripts.ctad_2026.build", "--strict"]);

  console.log("\n== Python verification ==");
  run("python3", ["-m", "unittest"]);

  console.log("\n== Program validation ==");
  run(
    "node",
    ["scripts/check-program.ts", ".programs/ctad-2026.json"],
    APP_ROOT,
  );

  console.log("\n== App verification ==");
  run("pnpm", ["run", "check"], APP_ROOT);
  run("pnpm", ["run", "test"], APP_ROOT);
}

function reconcileProduction(): void {
  console.log("\n== Production identity review ==");
  const catalog = parseConferenceCatalog(accessJson("/api/catalog"));
  const current = conferenceById(catalog, "ctad-2026");
  if (!current) {
    console.log(
      "CTAD is not published yet; no existing identity to reconcile.",
    );
    return;
  }

  const temporary = mkdtempSync(join(tmpdir(), "ctad-refresh-"));
  try {
    const baselinePath = join(temporary, "program.json");
    const snapshotPath = join(temporary, "notebook.json");
    writeFileSync(baselinePath, accessText(programPath(current)), "utf8");
    writeFileSync(
      snapshotPath,
      accessText("/api/conferences/ctad-2026/notebook/export.json"),
      "utf8",
    );
    const args = [
      "-m",
      "scripts.ctad_2026.reconcile",
      baselinePath,
      CANDIDATE,
      "--notebook-snapshot",
      snapshotPath,
      "--strict",
      "--output",
      CANDIDATE,
    ];
    run("python3", args);
    console.log("\n== Reconciled program validation ==");
    run(
      "node",
      ["scripts/check-program.ts", ".programs/ctad-2026.json"],
      APP_ROOT,
    );
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}

function publish(): void {
  build();
  reconcileProduction();

  console.log("\n== Publish CTAD candidate ==");
  run(
    "node",
    ["scripts/publish-program.ts", ".programs/ctad-2026.json"],
    APP_ROOT,
  );

  console.log("\n== Production read-back ==");
  const candidate = parseConferenceProgram(
    JSON.parse(readFileSync(CANDIDATE, "utf8")) as unknown,
  );
  const expectedHash = programContentHash(JSON.stringify(candidate));
  const catalog = parseConferenceCatalog(accessJson("/api/catalog"));
  const published = conferenceById(catalog, candidate.conference.id);
  if (published?.program_hash !== expectedHash) {
    throw new Error(
      `production catalog did not promote ${candidate.conference.id}@${expectedHash}`,
    );
  }
  const productionProgram = parseConferenceProgram(
    accessJson(programPath(published)),
  );
  const actualHash = programContentHash(JSON.stringify(productionProgram));
  if (actualHash !== expectedHash) {
    throw new Error(
      `production program hash is ${actualHash}, expected ${expectedHash}`,
    );
  }
  const snapshot = accessJson(
    "/api/conferences/ctad-2026/notebook/export.json",
  );
  if (
    typeof snapshot !== "object" ||
    snapshot === null ||
    !("conference_id" in snapshot) ||
    snapshot.conference_id !== candidate.conference.id ||
    !("program_version" in snapshot) ||
    snapshot.program_version !== expectedHash
  ) {
    throw new Error(
      "production notebook does not reference the new CTAD program",
    );
  }
  console.log(`verified ${candidate.conference.id}@${expectedHash}`);
}

const action = process.argv[2];
if (action === "build") {
  if (process.argv.length > 3) {
    throw new Error("ctad:build does not accept arguments");
  }
  build();
} else if (action === "publish") {
  if (process.argv.length > 3) {
    throw new Error("ctad:publish does not accept arguments");
  }
  publish();
} else {
  throw new Error("usage: ctad-workflow.ts <build|publish>");
}
