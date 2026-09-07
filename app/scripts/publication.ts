import { createHash } from "node:crypto";

import { AwsClient } from "aws4fetch";

import {
  CATALOG_KEY,
  CONFERENCE_CATALOG_SCHEMA_VERSION,
  conferenceById,
  parseConferenceCatalog,
  programKey,
  type ConferenceCatalog,
} from "../src/shared/catalog.ts";
import type { ConferenceProgram } from "../src/shared/program.ts";

const EMPTY_CATALOG: ConferenceCatalog = {
  schema_version: CONFERENCE_CATALOG_SCHEMA_VERSION,
  conferences: [],
};

export interface R2PublicationConfig {
  accountId: string;
  accessKeyId: string;
  secretAccessKey: string;
  bucket: string;
}

export interface PublicationResult {
  hash: string;
  changed: boolean;
}

export function programContentHash(programJson: string): string {
  return createHash("sha256").update(programJson).digest("hex");
}

export function catalogWithProgram(
  catalog: ConferenceCatalog,
  program: ConferenceProgram,
  hash: string,
): ConferenceCatalog {
  const entry = { ...program.conference, program_hash: hash };
  const existing = catalog.conferences.findIndex(
    (conference) => conference.id === entry.id,
  );
  const conferences = [...catalog.conferences];
  if (existing >= 0) conferences[existing] = entry;
  else conferences.push(entry);
  return { ...catalog, conferences };
}

/** Upload an immutable program, then update the catalog. Run one publisher at a time. */
export async function publishProgram(
  program: ConferenceProgram,
  config: R2PublicationConfig,
): Promise<PublicationResult> {
  const client = new AwsClient({
    service: "s3",
    region: "auto",
    accessKeyId: config.accessKeyId,
    secretAccessKey: config.secretAccessKey,
  });
  const programJson = JSON.stringify(program);
  const hash = programContentHash(programJson);
  const key = programKey(program.conference.id, hash);
  const catalog = await readCatalog(client, config);
  const current = conferenceById(catalog, program.conference.id);
  const next = catalogWithProgram(catalog, program, hash);

  if (
    JSON.stringify(current) ===
    JSON.stringify(conferenceById(next, program.conference.id))
  ) {
    await verifyProgramObject(client, config, key, programJson);
    return { hash, changed: false };
  }

  const upload = await r2Fetch(client, config, key, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "private, max-age=31536000, immutable",
      "If-None-Match": "*",
    },
    body: programJson,
  });
  if (upload.status === 412) {
    await verifyProgramObject(client, config, key, programJson);
  } else if (!upload.ok) {
    throw await r2Error("upload program", upload);
  } else {
    await verifyProgramObject(client, config, key, programJson);
  }

  const promotion = await r2Fetch(client, config, CATALOG_KEY, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "private, max-age=0, must-revalidate",
    },
    body: JSON.stringify(next),
  });
  if (!promotion.ok) throw await r2Error("promote catalog", promotion);

  const published = await readCatalog(client, config);
  if (conferenceById(published, program.conference.id)?.program_hash !== hash) {
    throw new Error("catalog read-back did not contain the promoted revision");
  }
  return { hash, changed: true };
}

async function readCatalog(
  client: AwsClient,
  config: R2PublicationConfig,
): Promise<ConferenceCatalog> {
  const response = await r2Fetch(client, config, CATALOG_KEY);
  if (response.status === 404) {
    return EMPTY_CATALOG;
  }
  if (!response.ok) throw await r2Error("read catalog", response);
  return parseConferenceCatalog(await response.json());
}

async function requiredObject(
  client: AwsClient,
  config: R2PublicationConfig,
  key: string,
): Promise<Response> {
  const response = await r2Fetch(client, config, key);
  if (!response.ok) throw await r2Error(`read ${key}`, response);
  return response;
}

async function verifyProgramObject(
  client: AwsClient,
  config: R2PublicationConfig,
  key: string,
  expected: string,
): Promise<void> {
  const object = await requiredObject(client, config, key);
  if ((await object.text()) !== expected) {
    throw new Error(`immutable object content mismatch at ${key}`);
  }
}

function r2Fetch(
  client: AwsClient,
  config: R2PublicationConfig,
  key: string,
  init?: RequestInit,
): Promise<Response> {
  const url = new URL(
    `/${encodeURIComponent(config.bucket)}/${key}`,
    `https://${config.accountId}.r2.cloudflarestorage.com`,
  );
  return client.fetch(url, init);
}

async function r2Error(action: string, response: Response): Promise<Error> {
  const detail = (await response.text()).slice(0, 500);
  return new Error(
    `${action} failed: HTTP ${response.status}${detail ? `: ${detail}` : ""}`,
  );
}
