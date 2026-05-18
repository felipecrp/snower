export type SetKind = 'start' | 'backward' | 'forward' | 'orphan';
export type Verdict = 'accept' | 'reject';
export type CriterionKind = 'include' | 'exclude';

export interface Researcher {
  email: string;
  name: string;
  assignment_percentage?: number;
}

export interface ResearcherInput extends Researcher {
  previous_email?: string | null;
}

export interface GitUser {
  name: string | null;
  email: string | null;
}

export interface Criterion {
  id: string;
  kind: CriterionKind;
  description: string;
}

export interface CriterionInput extends Criterion {
  previous_id?: string | null;
}

export interface Phase {
  id: string;
  description: string;
}

export interface PhaseInput extends Phase {
  previous_id?: string | null;
}

export interface ProviderConfig {
  name: string;
  enabled: boolean;
  options: Record<string, string>;
}

export interface Project {
  name: string;
  description?: string | null;
  researchers: Researcher[];
  criteria: Criterion[];
  phases: Phase[];
  providers: ProviderConfig[];
}

export interface Work {
  bib_key: string;
  title: string;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  doi?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  abstract?: string | null;
  last_backward_snowballed_at?: string | null;
  last_forward_snowballed_at?: string | null;
  last_backward_found?: number | null;
  last_forward_found?: number | null;
  has_local_pdf?: boolean;
}

export interface ReviewSet {
  id: string;
  kind: SetKind;
  iteration: number;
  works: Work[];
}

export interface Decision {
  bib_id: string;
  researcher_id: string;
  verdict: Verdict;
  criterion_id?: string | null;
  phase_id?: string | null;
  note?: string | null;
  decided_at: string;
}

export interface Resolution {
  bib_id: string;
  verdict: Verdict;
  by: string;
  note?: string | null;
  resolved_at: string;
}

export interface DecisionsResponse {
  decisions: Decision[];
  resolutions: Resolution[];
}

export interface DecisionInput {
  verdict: Verdict;
  criterion_id?: string | null;
  phase_id?: string | null;
  note?: string | null;
}

export interface Bidding {
  researcher_id: string;
  work_ids: string[];
}

export interface BiddingRunSummary {
  set_id: string;
  total_works: number;
  per_researcher: Record<string, number>;
  overlap_pct: number;
}

export interface WorkspaceInfo {
  path: string;
  name: string;
  researcher_email?: string | null;
}

export interface RecentProject {
  path: string;
  name: string;
  description?: string | null;
}

export interface ProjectInfoInput {
  name: string;
  description?: string | null;
}
