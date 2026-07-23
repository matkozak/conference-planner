import {
  CATALOG_KEY,
  parseConferenceCatalog,
  programKey,
  type ConferenceCatalog,
} from "../shared/catalog";
import type { ConferenceProgram } from "../shared/program";

const MAX_CATALOG_BYTES = 128 * 1024;
const CONFERENCE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const CONTENT_HASH = /^[a-f0-9]{64}$/;

export interface StoredCatalog {
  catalog: ConferenceCatalog;
  etag: string;
  httpEtag: string;
}

/** Load and validate the current publication pointer from the private bucket. */
export async function loadCatalog(bucket: R2Bucket): Promise<StoredCatalog> {
  const object = await bucket.get(CATALOG_KEY);
  if (!object) throw new Error("program catalog is not published");
  if (object.size > MAX_CATALOG_BYTES) {
    throw new Error(`program catalog exceeds ${MAX_CATALOG_BYTES} bytes`);
  }
  return {
    catalog: parseConferenceCatalog(await object.json<unknown>()),
    etag: object.etag,
    httpEtag: object.httpEtag,
  };
}

/** Stream the small current catalog with browser revalidation. */
export async function catalogResponse(
  bucket: R2Bucket,
  request: Request,
): Promise<Response> {
  const stored = await loadCatalog(bucket);
  if (request.headers.get("If-None-Match") === stored.httpEtag) {
    return new Response(null, {
      status: 304,
      headers: {
        ETag: stored.httpEtag,
        "Cache-Control": "private, max-age=0, must-revalidate",
      },
    });
  }
  return Response.json(stored.catalog, {
    headers: {
      ETag: stored.httpEtag,
      "Cache-Control": "private, max-age=0, must-revalidate",
    },
  });
}

/** Stream one immutable program object without buffering it in Worker memory. */
export async function programResponse(
  bucket: R2Bucket,
  conferenceId: string,
  hash: string,
  request: Request,
): Promise<Response> {
  if (!CONFERENCE_ID.test(conferenceId) || !CONTENT_HASH.test(hash)) {
    return new Response("Not Found", { status: 404 });
  }
  const object = await bucket.get(programKey(conferenceId, hash));
  if (!object) return new Response("Not Found", { status: 404 });

  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "private, max-age=31536000, immutable");
  headers.set("ETag", object.httpEtag);
  if (request.headers.get("If-None-Match") === object.httpEtag) {
    return new Response(null, { status: 304, headers });
  }
  return new Response(object.body, { headers });
}

/** Parse the current program for server-side exports that need title joins. */
export async function loadCurrentProgram(
  bucket: R2Bucket,
  conferenceId: string,
  hash: string,
): Promise<ConferenceProgram> {
  const object = await bucket.get(programKey(conferenceId, hash));
  if (!object) {
    throw new Error(`program object is missing for ${conferenceId}@${hash}`);
  }
  return object.json<ConferenceProgram>();
}
