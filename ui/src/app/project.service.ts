import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { Decision, Project, ReviewSet, WorkspaceInfo } from './models';

const LAST_PROJECT_KEY = 'snow:last-project';

@Injectable({ providedIn: 'root' })
export class ProjectService {
  private readonly api = inject(ApiService);

  readonly project = signal<Project | null>(null);
  readonly sets = signal<ReviewSet[]>([]);
  readonly allDecisions = signal<Record<string, Decision[]>>({});
  readonly error = signal<string | null>(null);
  readonly pendingSetIds = signal<ReadonlySet<string>>(new Set());
  readonly workspace = signal<WorkspaceInfo | null>(null);
  readonly workspaceLoaded = signal(false);

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
    this.api.getWorkspace().subscribe({
      next: (w) => {
        if (w) {
          this.applyWorkspace(w);
          return;
        }
        const lastPath = this.lastProjectPath();
        if (lastPath) {
          this.api.openProject(lastPath).subscribe({
            next: (opened) => this.applyWorkspace(opened),
            error: () => this.finishBootstrap(null),
          });
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
    this.rememberProjectPath(w.path);
    this.finishBootstrap(w);
    this.refresh();
  }

  refresh(): void {
    this.api.getProject().subscribe({
      next: (p) => {
        this.project.set(p);
        document.title = `Snow - ${p.name}`;
      },
      error: (e) => this.error.set(`Failed to load project: ${e.message}`),
    });
    this.api.listSets().subscribe({
      next: (sets) => {
        this.sets.set(sets);
        sets.forEach((s) => this.loadDecisionsForSet(s.id));
      },
      error: (e) => this.error.set(`Failed to load sets: ${e.message}`),
    });
  }

  private finishBootstrap(w: WorkspaceInfo | null): void {
    this.workspace.set(w);
    this.workspaceLoaded.set(true);
  }

  private lastProjectPath(): string | null {
    try {
      return localStorage.getItem(LAST_PROJECT_KEY);
    } catch {
      return null;
    }
  }

  private rememberProjectPath(path: string): void {
    try {
      localStorage.setItem(LAST_PROJECT_KEY, path);
    } catch {
      // Ignore storage errors (private mode, quota, etc.)
    }
  }

  loadDecisionsForSet(setId: string): void {
    this.api.getDecisions(setId).subscribe({
      next: (r) => this.allDecisions.update((all) => ({ ...all, [setId]: r.decisions })),
    });
  }

  updateDecisionsForSet(setId: string, decisions: Decision[]): void {
    this.allDecisions.update((all) => ({ ...all, [setId]: decisions }));
  }
}
