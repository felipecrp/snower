import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Criterion,
  CriterionInput,
  Decision,
  DecisionInput,
  DecisionsResponse,
  Project,
  Researcher,
  ResearcherInput,
  ReviewSet,
  SetKind,
} from './models';
import { ResearcherService } from './researcher.service';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly researcher = inject(ResearcherService);

  getProject(): Observable<Project> {
    return this.http.get<Project>('/api/project');
  }

  replaceResearchers(researchers: ResearcherInput[]): Observable<Researcher[]> {
    return this.http.put<Researcher[]>('/api/project/researchers', researchers);
  }

  replaceCriteria(criteria: CriterionInput[]): Observable<Criterion[]> {
    return this.http.put<Criterion[]>('/api/project/criteria', criteria);
  }

  listSets(): Observable<ReviewSet[]> {
    return this.http.get<ReviewSet[]>('/api/sets');
  }

  getSet(setId: string): Observable<ReviewSet> {
    return this.http.get<ReviewSet>(`/api/sets/${setId}`);
  }

  startSnowballing(setId: string, kind: Exclude<SetKind, 'start'>): Observable<ReviewSet> {
    return this.http.post<ReviewSet>(`/api/sets/${setId}/snowballing/${kind}`, {});
  }

  runGlobalSnowballing(kind: Exclude<SetKind, 'start'>): Observable<ReviewSet[]> {
    return this.http.post<ReviewSet[]>(`/api/snowballing/${kind}`, {});
  }

  getDecisions(setId: string): Observable<DecisionsResponse> {
    return this.http.get<DecisionsResponse>(`/api/sets/${setId}/decisions`);
  }

  upsertDecision(setId: string, workId: string, body: DecisionInput): Observable<Decision> {
    return this.http.put<Decision>(
      `/api/sets/${setId}/decisions/${encodeURIComponent(workId)}`,
      body,
      { headers: this.researcherHeaders() },
    );
  }

  deleteDecision(setId: string, workId: string): Observable<void> {
    return this.http.delete<void>(
      `/api/sets/${setId}/decisions/${encodeURIComponent(workId)}`,
      { headers: this.researcherHeaders() },
    );
  }

  private researcherHeaders(): HttpHeaders {
    const id = this.researcher.activeId();
    let headers = new HttpHeaders();
    if (id) headers = headers.set('X-Researcher-Id', id);
    return headers;
  }
}
