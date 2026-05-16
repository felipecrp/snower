export type SetKind = 'start' | 'backward' | 'forward' | 'orphan';
export type Verdict = 'accept' | 'reject';
export type CriterionKind = 'include' | 'exclude';

export interface Researcher {
  id: string;
  name: string;
  email?: string | null;
}

export interface ResearcherInput extends Researcher {
  previous_id?: string | null;
}

export interface Criterion {
  id: string;
  kind: CriterionKind;
  description: string;
}

export interface CriterionInput extends Criterion {
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
  providers: ProviderConfig[];
}

export interface Work {
  id: string;
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
}

export interface ReviewSet {
  id: string;
  kind: SetKind;
  iteration: number;
  works: Work[];
}

export interface Decision {
  work_id: string;
  researcher_id: string;
  verdict: Verdict;
  criterion_id?: string | null;
  note?: string | null;
  decided_at: string;
}

export interface Resolution {
  work_id: string;
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
  note?: string | null;
}

export interface WorkspaceInfo {
  path: string;
  name: string;
}

export interface ProjectInfoInput {
  name: string;
  description?: string | null;
  openalex_email?: string | null;
}
