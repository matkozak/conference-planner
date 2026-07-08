/**
 * The immutable conference program, produced from the scraped dump by
 * scripts/build-program.ts and served as a static asset. Empty/absent fields
 * are omitted entirely to keep the payload small — hence all the optionals.
 */
export interface Program {
  /** Content hash of the payload, also embedded in the asset filename. */
  version: string;
  /** Sorted unique ISO dates covered by the program. */
  days: string[];
  sessions: Session[];
  /** Keyed by EventPilot person id. */
  people: Record<string, Person>;
}

export interface Person {
  name: string;
  org?: string;
}

/** A talk within a session. Times are ISO 8601 with venue offset. */
export interface Presentation {
  id: string;
  title: string;
  starts_at?: string;
  ends_at?: string;
  location?: string;
  speaker_ids?: string[];
  /**
   * Author/affiliation block and abstract. Sanitized HTML restricted to bare
   * formatting tags (b/br/sup/sub/i/em/strong/p) — safe to render directly.
   */
  description?: string;
}

/** A parent session; a Presentation plus scheduling context and children. */
export interface Session extends Presentation {
  date: string;
  category?: string;
  session_number?: string;
  presentations: Presentation[];
}
