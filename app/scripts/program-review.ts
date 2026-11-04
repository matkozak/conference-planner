import type { NotebookSnapshot } from "../src/shared/notebook.ts";
import type {
  ConferenceProgram,
  Presentation,
  Session,
} from "../src/shared/program.ts";
import { programContentHash } from "./publication.ts";

const COMPARE_FIELDS = [
  "kind",
  "title",
  "date",
  "starts_at",
  "ends_at",
  "location",
  "parent_id",
  "presentation_ids",
  "speaker_ids",
  "description_html",
] as const;

type CompareField = (typeof COMPARE_FIELDS)[number];

interface ItemRecord {
  id: string;
  kind: Session["kind"] | Presentation["kind"];
  title: string;
  date: string;
  starts_at: string;
  ends_at: string;
  location: string;
  parent_id: string;
  presentation_ids: string[];
  speaker_ids: string[];
  description_html: string;
}

export interface ReferenceCounts {
  notes: number;
  rsvps: number;
}

interface ReferencedItemRecord extends ItemRecord {
  references: ReferenceCounts;
}

export interface ModifiedItem {
  id: string;
  kind: ItemRecord["kind"];
  old_title: string;
  new_title: string;
  fields: CompareField[];
  references: ReferenceCounts;
}

export interface ProgramReview {
  conference_id: string;
  baseline_hash: string;
  candidate_hash: string;
  summary: {
    stable_ids: number;
    added_ids: number;
    removed_ids: number;
    modified_ids: number;
    possible_id_reuse: number;
    items_with_user_content: number;
  };
  added: ItemRecord[];
  removed: ReferencedItemRecord[];
  modified: ModifiedItem[];
  possible_id_reuse: ModifiedItem[];
  items_with_user_content: (ReferencedItemRecord | ModifiedItem)[];
  orphaned_notebook_ids: string[];
}

/** Compare a candidate with its published baseline and current user content. */
export function reviewProgramUpdate(
  baseline: ConferenceProgram,
  candidate: ConferenceProgram,
  snapshotValue: unknown,
): ProgramReview {
  const conferenceId = baseline.conference.id;
  if (candidate.conference.id !== conferenceId) {
    throw new Error(
      `candidate conference ${candidate.conference.id} does not match baseline ${conferenceId}`,
    );
  }

  const baselineHash = programContentHash(JSON.stringify(baseline));
  const snapshot = parseNotebookSnapshot(
    snapshotValue,
    conferenceId,
    baselineHash,
  );
  const references = snapshotReferences(snapshot);
  const oldItems = itemRecords(baseline);
  const newItems = itemRecords(candidate);
  const oldIds = new Set(oldItems.keys());
  const newIds = new Set(newItems.keys());
  const counts = (id: string): ReferenceCounts =>
    references.get(id) ?? { notes: 0, rsvps: 0 };

  const added = [...newIds]
    .filter((id) => !oldIds.has(id))
    .sort()
    .map((id) => requiredMapValue(newItems, id));
  const removed = [...oldIds]
    .filter((id) => !newIds.has(id))
    .sort()
    .map((id) => ({
      ...requiredMapValue(oldItems, id),
      references: counts(id),
    }));
  const modified: ModifiedItem[] = [];
  const possibleIdReuse: ModifiedItem[] = [];

  for (const id of [...oldIds].filter((value) => newIds.has(value)).sort()) {
    const oldItem = requiredMapValue(oldItems, id);
    const newItem = requiredMapValue(newItems, id);
    const fields = changedFields(oldItem, newItem);
    if (fields.length === 0) continue;
    const row: ModifiedItem = {
      id,
      kind: oldItem.kind,
      old_title: oldItem.title,
      new_title: newItem.title,
      fields,
      references: counts(id),
    };
    modified.push(row);
    if (possibleIdentityReuse(oldItem, newItem)) possibleIdReuse.push(row);
  }

  const itemsWithUserContent = [...removed, ...modified].filter(
    (item) => referenceTotal(item.references) > 0,
  );
  return {
    conference_id: conferenceId,
    baseline_hash: baselineHash,
    candidate_hash: programContentHash(JSON.stringify(candidate)),
    summary: {
      stable_ids: [...oldIds].filter((id) => newIds.has(id)).length,
      added_ids: added.length,
      removed_ids: removed.length,
      modified_ids: modified.length,
      possible_id_reuse: possibleIdReuse.length,
      items_with_user_content: itemsWithUserContent.length,
    },
    added,
    removed,
    modified,
    possible_id_reuse: possibleIdReuse,
    items_with_user_content: itemsWithUserContent,
    orphaned_notebook_ids: [...references.keys()]
      .filter((id) => !oldIds.has(id))
      .sort(),
  };
}

/** Identity reuse cannot be waived; referenced content changes require review. */
export function publicationBlockers(
  review: ProgramReview,
  allowedContentChanges: ReadonlySet<string>,
): string[] {
  const blockers = review.possible_id_reuse.map(
    (item) => `${item.id}: possible item ID reuse`,
  );
  const reusedIds = new Set(review.possible_id_reuse.map((item) => item.id));
  for (const item of review.removed) {
    if (referenceTotal(item.references) > 0) {
      blockers.push(
        `${item.id}: removed item has ${formatReferences(item.references)}`,
      );
    }
  }
  for (const item of review.modified) {
    if (
      !reusedIds.has(item.id) &&
      !allowedContentChanges.has(item.id) &&
      referenceTotal(item.references) > 0
    ) {
      blockers.push(
        `${item.id}: changed item has ${formatReferences(item.references)}`,
      );
    }
  }
  return blockers;
}

export function renderProgramReview(review: ProgramReview): string {
  const { summary } = review;
  const lines = [
    `# Program identity review: ${review.conference_id}`,
    "",
    `- Stable IDs: ${summary.stable_ids}`,
    `- Added IDs: ${summary.added_ids}`,
    `- Removed IDs: ${summary.removed_ids}`,
    `- Modified IDs: ${summary.modified_ids}`,
    `- Possible item ID reuse: ${summary.possible_id_reuse}`,
    `- Changed/removed items with user content: ${summary.items_with_user_content}`,
  ];
  const section = <T>(title: string, rows: T[], format: (row: T) => string) => {
    if (rows.length === 0) return;
    lines.push("", `## ${title}`, "", ...rows.map((row) => `- ${format(row)}`));
  };
  section(
    "Possible item ID reuse",
    review.possible_id_reuse,
    (item) =>
      `\`${item.id}\`: ${item.old_title} → ${item.new_title} (${formatReferences(item.references)})`,
  );
  section(
    "Removed IDs",
    review.removed,
    (item) =>
      `\`${item.id}\`: ${item.title} (${formatReferences(item.references)})`,
  );
  section(
    "Modified IDs",
    review.modified,
    (item) =>
      `\`${item.id}\`: ${item.fields.join(", ")} (${formatReferences(item.references)})`,
  );
  section("Added IDs", review.added, (item) => `\`${item.id}\`: ${item.title}`);
  if (review.orphaned_notebook_ids.length > 0) {
    lines.push(
      "",
      "> Warning: the notebook already references IDs absent from the baseline: " +
        review.orphaned_notebook_ids.join(", "),
    );
  }
  return `${lines.join("\n")}\n`;
}

function itemRecords(program: ConferenceProgram): Map<string, ItemRecord> {
  const records = new Map<string, ItemRecord>();
  for (const session of program.sessions) {
    records.set(
      session.id,
      itemRecord(session, session.date, "", session.presentations),
    );
    for (const presentation of session.presentations) {
      records.set(
        presentation.id,
        itemRecord(presentation, session.date, session.id, []),
      );
    }
  }
  return records;
}

function itemRecord(
  item: Session | Presentation,
  date: string,
  parentId: string,
  presentations: Presentation[],
): ItemRecord {
  return {
    id: item.id,
    kind: item.kind,
    title: item.title,
    date,
    starts_at: item.starts_at ?? "",
    ends_at: item.ends_at ?? "",
    location: item.location ?? "",
    parent_id: parentId,
    presentation_ids: presentations.map((presentation) => presentation.id),
    speaker_ids: [...(item.speaker_ids ?? [])].sort(),
    description_html: item.description_html ?? "",
  };
}

function changedFields(
  oldItem: ItemRecord,
  newItem: ItemRecord,
): CompareField[] {
  return COMPARE_FIELDS.filter(
    (field) =>
      JSON.stringify(oldItem[field]) !== JSON.stringify(newItem[field]),
  );
}

function possibleIdentityReuse(
  oldItem: ItemRecord,
  newItem: ItemRecord,
): boolean {
  if (oldItem.kind !== newItem.kind) return true;
  const oldChildren = new Set(oldItem.presentation_ids);
  const newChildren = new Set(newItem.presentation_ids);
  const childrenReplaced =
    oldChildren.size > 0 &&
    newChildren.size > 0 &&
    [...oldChildren].every((id) => !newChildren.has(id));
  const speakersOverlap = oldItem.speaker_ids.some((id) =>
    newItem.speaker_ids.includes(id),
  );
  return (
    childrenReplaced ||
    (stringSimilarity(
      normalizeTitle(oldItem.title),
      normalizeTitle(newItem.title),
    ) < 0.35 &&
      !speakersOverlap)
  );
}

function normalizeTitle(value: string): string {
  return [...value.toLocaleLowerCase().matchAll(/[\p{L}\p{N}]+/gu)]
    .map((match) => match[0])
    .join(" ");
}

function stringSimilarity(left: string, right: string): number {
  if (left === right) return 1;
  const longest = Math.max(left.length, right.length);
  if (longest === 0) return 1;
  const previous = Array.from(
    { length: right.length + 1 },
    (_, index) => index,
  );
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    const current = [leftIndex];
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      current[rightIndex] = Math.min(
        (current[rightIndex - 1] ?? 0) + 1,
        (previous[rightIndex] ?? 0) + 1,
        (previous[rightIndex - 1] ?? 0) +
          (left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1),
      );
    }
    previous.splice(0, previous.length, ...current);
  }
  return 1 - (previous[right.length] ?? longest) / longest;
}

function parseNotebookSnapshot(
  value: unknown,
  conferenceId: string,
  baselineHash: string,
): NotebookSnapshot {
  if (!isRecord(value)) throw new Error("notebook snapshot must be an object");
  if (value.conference_id !== conferenceId) {
    throw new Error(`notebook snapshot conference_id must be ${conferenceId}`);
  }
  if (value.program_version !== baselineHash) {
    throw new Error(
      "notebook snapshot program_version does not match the baseline",
    );
  }
  if (typeof value.exported_at !== "string") {
    throw new Error("notebook snapshot exported_at must be a string");
  }
  if (!Array.isArray(value.notes) || !Array.isArray(value.rsvps)) {
    throw new Error("notebook snapshot notes and rsvps must be arrays");
  }
  for (const [kind, rows] of [
    ["note", value.notes],
    ["rsvp", value.rsvps],
  ] as const) {
    for (const row of rows) {
      if (!isRecord(row) || typeof row.item_id !== "string" || !row.item_id) {
        throw new Error(`${kind} item_id must be a non-empty string`);
      }
    }
  }
  return value as unknown as NotebookSnapshot;
}

function snapshotReferences(
  snapshot: NotebookSnapshot,
): Map<string, ReferenceCounts> {
  const counts = new Map<string, ReferenceCounts>();
  const increment = (id: string, key: keyof ReferenceCounts) => {
    const current = counts.get(id) ?? { notes: 0, rsvps: 0 };
    current[key] += 1;
    counts.set(id, current);
  };
  for (const note of snapshot.notes) increment(note.item_id, "notes");
  for (const rsvp of snapshot.rsvps) increment(rsvp.item_id, "rsvps");
  return counts;
}

function referenceTotal(references: ReferenceCounts): number {
  return references.notes + references.rsvps;
}

function formatReferences(references: ReferenceCounts): string {
  return `${references.notes} note(s), ${references.rsvps} RSVP(s)`;
}

function requiredMapValue<K, V>(map: Map<K, V>, key: K): V {
  const value = map.get(key);
  if (value === undefined)
    throw new Error(`missing map value for ${String(key)}`);
  return value;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
