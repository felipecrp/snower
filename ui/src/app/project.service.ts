import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { Decision, Project, RecentProject, ReviewSet, WorkspaceInfo } from './models';
import { ResearcherService } from './researcher.service';

type RawDecision = Decision & { bib_key?: string; work_id?: string };

@Injectable({ providedIn: 'root' })
export class ProjectService {
  private readonly api = inject(ApiService);
  private readonly researcherSvc = inject(ResearcherService);

  readonly project = signal<Project | null>(null);
  readonly sets = signal<ReviewSet[]>([]);
  readonly allDecisions = signal<Record<string, Decision[]>>({});
  readonly error = signal<string | null>(null);
  readonly pendingSetIds = signal<ReadonlySet<string>>(new Set());
  readonly workspace = signal<WorkspaceInfo | null>(null);
  readonly workspaceLoaded = signal(false);
  readonly recents = signal<RecentProject[]>([]);

  loadRecentProjects(): void {
    this.api.getRecentProjects().subscribe({
      next: (recents) => this.recents.set(recents),
      error: () => this.recents.set([]),
    });
  }

  rememberProject(entry: RecentProject): void {
    this.api.putRecentProject(entry).subscribe({
      next: (recents) => this.recents.set(recents),
    });
  }

  removeRecentProject(path: string): void {
    this.api.deleteRecentProject(path).subscribe({
      next: (recents) => this.recents.set(recents),
    });
  }

  markSetsPending(ids: Iterable<string>): void {
    this.pendingSetIds.update((current) => {
      const next = new Set(current);
      for (const id of ids) next.add(id);
      return next;
    });
  }

  clearSetsPending(ids: Iterable<string>): void {
    this.pendingSetIds.update((current) => {
      const next = new Set(current);
      for (const id of ids) next.delete(id);
      return next;
    });
  }

  ensurePlaceholderSet(id: string, kind: ReviewSet['kind'], iteration: number): void {
    this.sets.update((all) => {
      if (all.some((s) => s.id === id)) return all;
      const placeholder: ReviewSet = { id, kind, iteration, works: [] };
      return [...all, placeholder].sort((a, b) => a.id.localeCompare(b.id));
    });
  }

  bootstrapWorkspace(): void {
    this.loadRecentProjects();
    this.api.getWorkspace().subscribe({
      next: (w) => {
        if (w) {
          this.applyWorkspace(w);
        } else {
          this.finishBootstrap(null);
        }
      },
      error: (e) => {
        this.error.set(`Failed to load workspace: ${e.message}`);
        this.finishBootstrap(null);
      },
    });
  }

  applyWorkspace(w: WorkspaceInfo): void {
    this.rememberProject({ path: w.path, name: w.name });
    this.finishBootstrap(w);
    this.refresh(w.researcher_email);
  }

  refresh(autoSelectResearcherEmail?: string | null): void {
    this.api.getProject().subscribe({
      next: (p) => {
        this.project.set(p);
        document.title = `Snow - ${p.description || p.name}`;
        // Set researcher AFTER project loads so options exist in topbar select
        if (autoSelectResearcherEmail) {
          this.researcherSvc.set(autoSelectResearcherEmail);
        }
      },
      error: (e) => this.handleProjectError(e),
    });
    this.api.listSets().subscribe({
      next: (sets) => {
        this.sets.set(sets);
        sets.forEach((s) => this.loadDecisionsForSet(s.id));
      },
      error: (e) => this.handleProjectError(e),
    });
  }

  private handleProjectError(error: any): void {
    this.error.set(`Failed to load project: ${error.message}`);
  }

  private finishBootstrap(w: WorkspaceInfo | null): void {
    this.workspace.set(w);
    this.workspaceLoaded.set(true);
  }


  loadDecisionsForSet(setId: string): void {
    this.api.getDecisions(setId).subscribe({
      next: (r) => this.allDecisions.update((all) => ({ ...all, [setId]: this.normalizeDecisions(r.decisions) })),
      error: (e) => this.handleProjectError(e),
    });
  }

  updateDecisionsForSet(setId: string, decisions: Decision[]): void {
    this.allDecisions.update((all) => ({ ...all, [setId]: this.normalizeDecisions(decisions) }));
  }

  private normalizeDecisions(decisions: RawDecision[]): Decision[] {
    return decisions.map((d) => ({
      ...d,
      bib_id: d.bib_id ?? d.bib_key ?? d.work_id ?? '',
    }));
  }
}
