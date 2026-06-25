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
  decision: 'included' | 'excluded' | 'undecided';
  /** Assessment map embedded by GET /sets/{set}/papers (email → Assessment). */
  assessments?: AssessmentMap;
}

/** A compact set descriptor returned by GET /sets and used in the project summary. */
export interface SetSummary {
  name: string;
  round: number | null;
  count: number;
}

/** Whether a screening criterion marks inclusion or exclusion. */
export type CriterionType = 'inclusion' | 'exclusion';

/** A screening criterion belonging to the project. */
export interface Criterion {
  id: string;
  name: string;
  type: CriterionType;
}

/** A screening phase belonging to the project. */
export interface Phase {
  id: string;
  name: string;
}

/** A researcher registered on the project. */
export interface Researcher {
  email: string;
  name: string;
}

/** A recorded screening decision: which criterion and phase were applied. */
export interface Assessment {
  criterion: Criterion;
  phase: Phase;
  comment?: string | null;
}

/** Map of researcher email → Assessment for a single paper. */
export type AssessmentMap = Record<string, Assessment>;

/** The two available decision strategies. */
export type DecisionStrategy = 'majority' | 'consensus';

/** A summary of the current single project served by the backend. */
export interface ProjectSummary {
  name: string;
  folder: string;
  seeds: string[];
  sets: SetSummary[];
  criteria: Criterion[];
  phases: Phase[];
  researchers: Researcher[];
  decision_strategy: DecisionStrategy;
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

/** Returns true when the assessment's criterion marks inclusion. */
export function isIncluded(a: Assessment): boolean {
  return a.criterion.type === 'inclusion';
}
