import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  ImportResult,
  Paper,
  ScreeningResult,
  SetSummary,
  ProjectSummary,
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

  /** Get a summary of the current project (name, seeds, set counts). */
  getProjectSummary(): Observable<ProjectSummary> {
    return this.http.get<ProjectSummary>(`${this.baseUrl}/`);
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

  /** Include or exclude a paper (screening); returns bib_id and new included state. */
  screenPaper(bibId: string, included: boolean): Observable<ScreeningResult> {
    return this.http.patch<ScreeningResult>(
      `${this.baseUrl}/papers/${encodeURIComponent(bibId)}`,
      { included },
    );
  }
}
