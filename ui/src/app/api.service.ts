import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Bidding,
  BiddingRunSummary,
  Criterion,
  CriterionInput,
  Decision,
  DecisionInput,
  DecisionsResponse,
  GitUser,
  Phase,
  PhaseInput,
  Project,
  ProjectInfoInput,
  RecentProject,
  Researcher,
  ResearcherInput,
  ReviewSet,
  SetKind,
  Work,
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

  replacePhases(phases: PhaseInput[]): Observable<Phase[]> {
    return this.http.put<Phase[]>('/api/project/phases', phases);
  }

  listSets(): Observable<ReviewSet[]> {
    return this.http.get<ReviewSet[]>('/api/sets');
  }

  getSet(setId: string): Observable<ReviewSet> {
    return this.http.get<ReviewSet>(`/api/sets/${setId}`);
  }

  runSnowballing(): Observable<ReviewSet[]> {
    return this.http.post<ReviewSet[]>('/api/snowballing', {}, { headers: this.researcherHeaders() });
  }

  runGlobalSnowballing(kind: Exclude<SetKind, 'start'>, force = false): Observable<ReviewSet[]> {
    const params = force ? '?force=true' : '';
    return this.http.post<ReviewSet[]>(`/api/snowballing/${kind}${params}`, {}, { headers: this.researcherHeaders() });
  }

  runPaperSnowballing(kind: Exclude<SetKind, 'start'>, bibKey: string): Observable<ReviewSet[]> {
    return this.http.post<ReviewSet[]>(`/api/snowballing/${kind}/${encodeURIComponent(bibKey)}`, {}, { headers: this.researcherHeaders() });
  }

  getGitUser(): Observable<GitUser> {
    return this.http.get<GitUser>('/api/git-user');
  }

  importBib(setId: string, file: File): Observable<ReviewSet> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ReviewSet>(`/api/sets/${setId}/import`, form, {
      headers: this.researcherHeaders(),
    });
  }

  parseBib(setId: string, file: File): Observable<Work[]> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<Work[]>(`/api/sets/${setId}/parse-bib`, form);
  }

  importWork(setId: string, work: Work): Observable<Work> {
    return this.http.post<Work>(`/api/sets/${setId}/import-work`, work, {
      headers: this.researcherHeaders(),
    });
  }

  getWorkBibtex(bibKey: string): Observable<{ bibtex: string }> {
    return this.http.get<{ bibtex: string }>(`/api/works/${bibKey}/bibtex`);
  }

  putWorkBibtex(bibKey: string, bibtex: string): Observable<Work> {
    return this.http.put<Work>(`/api/works/${bibKey}/bibtex`, { bibtex });
  }

  getWorkspace(): Observable<WorkspaceInfo | null> {
    return this.http.get<WorkspaceInfo | null>('/api/workspace');
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

  recalculateOrphans(): Observable<ReviewSet[]> {
    return this.http.post<ReviewSet[]>('/api/orphans/recalculate', {});
  }

  deleteDecision(setId: string, workId: string): Observable<void> {
    return this.http.delete<void>(
      `/api/sets/${setId}/decisions/${encodeURIComponent(workId)}`,
      { headers: this.researcherHeaders() },
    );
  }

  getBiddings(setId: string): Observable<Bidding[]> {
    return this.http.get<Bidding[]>(`/api/sets/${setId}/bidding`);
  }

  addBid(setId: string, workId: string): Observable<Bidding> {
    return this.http.put<Bidding>(
      `/api/sets/${setId}/bidding/${encodeURIComponent(workId)}`,
      {},
      { headers: this.researcherHeaders() },
    );
  }

  removeBid(setId: string, workId: string): Observable<Bidding> {
    return this.http.delete<Bidding>(
      `/api/sets/${setId}/bidding/${encodeURIComponent(workId)}`,
      { headers: this.researcherHeaders() },
    );
  }

  runBidding(): Observable<BiddingRunSummary[]> {
    return this.http.post<BiddingRunSummary[]>('/api/bidding/run', {});
  }

  localPdfUrl(bib_key: string): string {
    return `/api/downloads/${encodeURIComponent(bib_key)}`;
  }

  getRecentProjects(): Observable<RecentProject[]> {
    return this.http.get<RecentProject[]>('/api/recent-projects');
  }

  putRecentProject(entry: RecentProject): Observable<RecentProject[]> {
    return this.http.put<RecentProject[]>('/api/recent-projects', entry);
  }

  deleteRecentProject(path: string): Observable<RecentProject[]> {
    return this.http.delete<RecentProject[]>('/api/recent-projects', { body: { path } });
  }

  private researcherHeaders(): HttpHeaders {
    const id = this.researcher.activeId();
    let headers = new HttpHeaders();
    if (id) headers = headers.set('X-Researcher-Id', id);
    return headers;
  }
}
