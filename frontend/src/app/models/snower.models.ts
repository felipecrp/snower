/**
 * Type definitions mirroring the Snower REST API payloads.
 *
 * These interfaces describe the JSON shapes returned by the FastAPI backend
 * (see doc/api.md). They are deliberately structural — only the fields the UI
 * consumes are typed strictly; open-ended maps keep the rest verbatim.
 */

/** A structured author name as returned by the API. */
export interface Author {
  family: string;
  given?: string | null;
  suffix?: string | null;
}

/** A bibliographic paper and a node in the citation graph. */
export interface Paper {
  entry_type: string;
  bib_id: string | null;
  title: string;
  authors: Author[];
  year?: number | null;
  abstract?: string | null;
  doi?: string | null;
  url?: string | null;
  fields: Record<string, string>;
  references: string[];
  citations: string[];
  included: boolean;
}

/** A compact set descriptor returned by GET /sets and used in the project summary. */
export interface SetSummary {
  name: string;
  round: number | null;
  count: number;
}

/** A summary of the current single project served by the backend. */
export interface ProjectSummary {
  name: string;
  seeds: string[];
  sets: SetSummary[];
}

/** Result of a screening (include/exclude) operation. */
export interface ScreeningResult {
  bib_id: string;
  included: boolean | null;
}

/** Outcome of a BibTeX import: ids imported and human-readable skipped entries. */
export interface ImportResult {
  imported: string[];
  skipped: string[];
}

/**
 * Build the set key for the `/sets/{set_name}/papers` route.
 * Special sets (``start_set``, ``orphans``) use their name directly;
 * directional sets use ``{name}-{round}``.
 */
export function setKey(set: { name: string; round: number | null }): string {
  return set.round !== null ? `${set.name}-${set.round}` : set.name;
}
