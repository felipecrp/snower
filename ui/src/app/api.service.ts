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
  ProjectInfoInput,
  Researcher,
  ResearcherInput,
  ReviewSet,
  SetKind,
  WorkspaceInfo,
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

  runSnowballing(): Observable<ReviewSet[]> {
    return this.http.post<ReviewSet[]>('/api/snowballing', {});
  }

  runGlobalSnowballing(kind: Exclude<SetKind, 'start'>, force = false): Observable<ReviewSet[]> {
    const params = force ? '?force=true' : '';
    return this.http.post<ReviewSet[]>(`/api/snowballing/${kind}${params}`, {});
  }

  runPaperSnowballing(kind: Exclude<SetKind, 'start'>, bibKey: string): Observable<ReviewSet[]> {
    return this.http.post<ReviewSet[]>(`/api/snowballing/${kind}/${encodeURIComponent(bibKey)}`, {});
  }

  importBib(setId: string, file: File): Observable<ReviewSet> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ReviewSet>(`/api/sets/${setId}/import`, form, {
      headers: this.researcherHeaders(),
    });
  }

  getWorkspace(): Observable<WorkspaceInfo> {
    return this.http.get<WorkspaceInfo>('/api/workspace');
  }

  newProject(path: string, name: string, description?: string): Observable<WorkspaceInfo> {
    return this.http.post<WorkspaceInfo>('/api/workspace/new', { path, name, description });
  }

  openProject(path: string): Observable<WorkspaceInfo> {
    return this.http.post<WorkspaceInfo>('/api/workspace/open', { path });
  }

  updateProjectInfo(body: ProjectInfoInput): Observable<Project> {
    return this.http.put<Project>('/api/project/info', body);
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
