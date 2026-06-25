import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  AssessmentMap,
  Criterion,
  DecisionStrategy,
  ImportResult,
  Paper,
  Phase,
  ProjectSummary,
  Researcher,
  SetSummary,
} from '../models/snower.models';

/**
 * HTTP gateway to the single-project Snower REST API.
 *
 * Every method maps to one backend route (see doc/api.md). The backend is
 * single-project, so no project id is threaded through these calls. Mutating
 * calls autosave server-side; callers refresh derived state by re-reading.
 */
@Injectable({ providedIn: 'root' })
export class SnowerService {
  /** Base URL of the running FastAPI server. */
  private readonly baseUrl = 'http://localhost:8000';
  private readonly http = inject(HttpClient);

  /** Get a summary of the current project (name, seeds, set counts, criteria, phases, researchers). */
  getProjectSummary(): Observable<ProjectSummary> {
    return this.http.get<ProjectSummary>(`${this.baseUrl}/`);
  }

  /** Update the project's decision strategy. Returns the updated project summary. */
  updateDecisionStrategy(strategy: DecisionStrategy): Observable<ProjectSummary> {
    return this.http.patch<ProjectSummary>(`${this.baseUrl}/`, { decision_strategy: strategy });
  }

  /** List every derived snowballing set. */
  getSets(): Observable<SetSummary[]> {
    return this.http.get<SetSummary[]>(`${this.baseUrl}/sets`);
  }

  /** List the papers belonging to a named set (e.g. `start-0`). */
  getPapersInSet(setName: string): Observable<Paper[]> {
    return this.http.get<Paper[]>(
      `${this.baseUrl}/sets/${encodeURIComponent(setName)}/papers`,
    );
  }

  /** List every paper in the project. */
  getPapers(): Observable<Paper[]> {
    return this.http.get<Paper[]>(`${this.baseUrl}/papers`);
  }

  /** Import papers from a raw BibTeX string, optionally registering them as seeds. */
  importBibtex(bibtex: string, asSeed = false): Observable<ImportResult> {
    return this.http.post<ImportResult>(`${this.baseUrl}/import`, {
      bibtex,
      as_seed: asSeed,
    });
  }

  /**
   * Record a screening assessment for a paper.
   * Returns the updated paper (including its decision and full assessment map).
   */
  assessPaper(
    bibId: string,
    body: { criterion_id: string; phase_id: string; researcher_email: string; comment?: string | null },
  ): Observable<Paper> {
    return this.http.patch<Paper>(
      `${this.baseUrl}/papers/${encodeURIComponent(bibId)}`,
      body,
    );
  }

  /** Get all assessments for a paper (email → Assessment). */
  getAssessments(bibId: string): Observable<AssessmentMap> {
    return this.http.get<AssessmentMap>(
      `${this.baseUrl}/papers/${encodeURIComponent(bibId)}/assessments`,
    );
  }

  /** Remove a researcher's assessment for a paper. Returns the updated paper. */
  removeAssessment(bibId: string, researcherEmail: string): Observable<Paper> {
    return this.http.delete<Paper>(
      `${this.baseUrl}/papers/${encodeURIComponent(bibId)}/assessments/${encodeURIComponent(researcherEmail)}`,
    );
  }

  // ----- Criteria CRUD ---------------------------------------------------------

  /** List all screening criteria. */
  getCriteria(): Observable<Criterion[]> {
    return this.http.get<Criterion[]>(`${this.baseUrl}/criteria`);
  }

  /** Create a new criterion. Returns 201 with no body; 409 on duplicate id. */
  createCriterion(c: { id: string; name: string; type: string }): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/criteria`, c);
  }

  /** Update an existing criterion (rename id and/or change name/type). Returns 204; 404/409 on error. */
  updateCriterion(originalId: string, c: Criterion): Observable<void> {
    return this.http.patch<void>(
      `${this.baseUrl}/criteria/${encodeURIComponent(originalId)}`,
      c,
    );
  }

  /** Delete a criterion. Returns 204 with no body; 404 if absent. */
  deleteCriterion(id: string): Observable<void> {
    return this.http.delete<void>(
      `${this.baseUrl}/criteria/${encodeURIComponent(id)}`,
    );
  }

  // ----- Phases CRUD -----------------------------------------------------------

  /** List all screening phases. */
  getPhases(): Observable<Phase[]> {
    return this.http.get<Phase[]>(`${this.baseUrl}/phases`);
  }

  /** Create a new phase. Returns 201 with no body; 409 on duplicate id. */
  createPhase(p: { id: string; name: string }): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/phases`, p);
  }

  /** Update an existing phase (rename id and/or change name). Returns 204; 404/409 on error. */
  updatePhase(originalId: string, p: Phase): Observable<void> {
    return this.http.patch<void>(
      `${this.baseUrl}/phases/${encodeURIComponent(originalId)}`,
      p,
    );
  }

  /** Delete a phase. Returns 204 with no body; 404 if absent. */
  deletePhase(id: string): Observable<void> {
    return this.http.delete<void>(
      `${this.baseUrl}/phases/${encodeURIComponent(id)}`,
    );
  }

  // ----- Researchers CRUD ------------------------------------------------------

  /** List all researchers. */
  getResearchers(): Observable<Researcher[]> {
    return this.http.get<Researcher[]>(`${this.baseUrl}/researchers`);
  }

  /** Create a new researcher. Returns 201 with no body; 409 on duplicate email. */
  createResearcher(r: { email: string; name: string }): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/researchers`, r);
  }

  /** Update an existing researcher (rename email and/or change name). Returns 204; 404/409 on error. */
  updateResearcher(originalEmail: string, r: Researcher): Observable<void> {
    return this.http.patch<void>(
      `${this.baseUrl}/researchers/${encodeURIComponent(originalEmail)}`,
      r,
    );
  }

  /** Delete a researcher. Returns 204 with no body; 404 if absent. */
  deleteResearcher(email: string): Observable<void> {
    return this.http.delete<void>(
      `${this.baseUrl}/researchers/${encodeURIComponent(email)}`,
    );
  }
}
