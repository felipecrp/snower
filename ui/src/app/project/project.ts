import { CommonModule } from '@angular/common';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api.service';
import {
  Criterion,
  CriterionInput,
  CriterionKind,
  Phase,
  PhaseInput,
  Researcher,
  ResearcherInput,
  WorkspaceInfo,
} from '../models';
import { ProjectService } from '../project.service';
import { ResearcherService } from '../researcher.service';

interface ResearcherRow extends Researcher {
  originalEmail: string;
  assignment_percentage: number;
}

interface CriterionRow extends Criterion {
  originalId: string;
}

interface PhaseRow extends Phase {
  originalId: string;
}

type Dialog = 'new' | 'open' | null;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PROJECT_NAME_RE = /^[a-zA-Z0-9_@-]+$/;

@Component({
  selector: 'app-project',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './project.html',
  styleUrl: './project.scss',
})
export class ProjectComponent {
  private readonly api = inject(ApiService);
  private readonly projectSvc = inject(ProjectService);
  private readonly researcherSvc = inject(ResearcherService);

  readonly workspace = signal<WorkspaceInfo | null>(null);
  readonly projectName = signal('');
  readonly projectDescription = signal('');
  readonly researchers = signal<ResearcherRow[]>([]);
  readonly criteria = signal<CriterionRow[]>([]);
  readonly phases = signal<PhaseRow[]>([]);
  readonly error = signal<string | null>(null);
  readonly saved = signal<string | null>(null);

  readonly assignmentPercentageSum = computed(() =>
    this.researchers().reduce((sum, r) => sum + (r.assignment_percentage ?? 100), 0),
  );
  readonly assignmentWarning = computed(() => {
    const sum = this.assignmentPercentageSum();
    return sum < 100 ? `Sum of bid percentages is ${sum}% — must be at least 100%.` : null;
  });
  readonly biddingCoverage = computed<Array<{ pct: number; n: number }>>(() => {
    if (!this.researchers().length) return [];
    const sum = this.assignmentPercentageSum();
    if (sum < 100) return [];
    const atLeast = (n: number) => Math.min(Math.max(0, sum - (n - 1) * 100), 100);
    const result: Array<{ pct: number; n: number }> = [];
    let n = 1;
    while (atLeast(n) > 0) {
      const pct = atLeast(n) - atLeast(n + 1);
      if (pct > 0) result.push({ pct, n });
      n++;
    }
    return result.reverse();
  });

  readonly currentResearcher = computed(() => {
    const email = this.researcherSvc.activeId();
    return this.researchers().find((r) => r.email === email) ?? null;
  });

  readonly dialog = signal<Dialog>(null);
  readonly dialogPath = signal('');
  readonly dialogName = signal('');
  readonly dialogDescription = signal('');
  readonly dialogWorking = signal(false);
  readonly dialogResolvedPath = computed(() => {
    const kind = this.dialog();
    const path = this.dialogPath().trim();
    if (kind !== 'new') return path;
    const name = this.dialogName().trim();
    return path && name ? this.joinPath(path, name) : '';
  });

  readonly criterionKinds: CriterionKind[] = ['include', 'exclude'];

  constructor() {
    this.refresh();
    effect(() => {
      if (this.projectSvc.workspaceLoaded() && !this.projectSvc.workspace() && !this.dialog()) {
        this.openDialog('open');
      }
    });
  }

  refresh(): void {
    this.api.getWorkspace().subscribe({
      next: (w) => this.workspace.set(w),
    });
    if (!this.projectSvc.workspace() && !this.projectSvc.workspaceLoaded()) {
      // App bootstrap will populate the project once a workspace is bound.
      return;
    }
    this.api.getProject().subscribe({
      next: (p) => {
        this.projectName.set(p.name);
        this.projectDescription.set(p.description ?? '');
        this.researchers.set(this.sortResearcherRows(p.researchers.map((r) => ({ ...r, originalEmail: r.email, assignment_percentage: r.assignment_percentage ?? 100 }))));
        this.criteria.set(this.sortCriterionRows(p.criteria.map((c) => ({ ...c, originalId: c.id }))));
        this.phases.set(this.sortPhaseRows(p.phases.map((ph) => ({ ...ph, originalId: ph.id }))));
      },
      error: (e) => {
        if (e.status !== 409) this.error.set(`Failed to load project: ${e.message}`);
      },
    });
  }

  saveProjectInfo(): void {
    this.error.set(null);
    this.saved.set(null);
    this.api.updateProjectInfo({ name: this.projectName(), description: this.projectDescription() || null }).subscribe({
      next: (p) => {
        this.projectName.set(p.name);
        this.projectDescription.set(p.description ?? '');
        this.projectSvc.project.set(p);
        document.title = `Snow - ${p.description || p.name}`;
        this.saved.set('Project info saved.');
      },
      error: (e) => this.error.set(`Failed to save project info: ${this.errorMessage(e)}`),
    });
  }

  openDialog(kind: 'new' | 'open'): void {
    this.dialog.set(kind);
    this.dialogPath.set('');
    this.dialogName.set('');
    this.dialogDescription.set('');
    this.error.set(null);
  }

  closeDialog(): void {
    this.dialog.set(null);
  }

  confirmDialog(): void {
    const kind = this.dialog();
    const path = this.dialogResolvedPath().trim();
    if (!path) { this.error.set('Path is required.'); return; }
    if (kind === 'new') {
      const name = this.dialogName().trim();
      if (!name) {
        this.error.set('Project name is required.');
        return;
      }
      if (!PROJECT_NAME_RE.test(name)) {
        this.error.set('Project name must use only letters, digits, `_`, `-`, or `@`.');
        return;
      }
    }
    this.dialogWorking.set(true);
    this.error.set(null);

    const obs$ = kind === 'new'
      ? this.api.newProject(path, this.dialogName().trim(), this.dialogDescription().trim() || undefined)
      : this.api.openProject(path);

    obs$.subscribe({
      next: (w) => {
        this.dialogWorking.set(false);
        this.dialog.set(null);
        this.workspace.set(w);
        this.projectSvc.applyWorkspace(w);
        this.refresh();
      },
      error: (e) => {
        this.dialogWorking.set(false);
        this.error.set(this.errorMessage(e));
      },
    });
  }

  async pickDirectory(): Promise<void> {
    if (!window.snowShell?.pickDirectory) {
      this.error.set('Directory picker is only available in Electron.');
      return;
    }
    const kind = this.dialog();
    const title = kind === 'new' ? 'Choose parent folder' : 'Choose project folder';
    const defaultPath = (kind === 'new' ? this.dialogPath() : this.dialogResolvedPath()).trim() || undefined;
    const pickedPath = await window.snowShell.pickDirectory({ title, defaultPath });
    if (!pickedPath) return;
    this.dialogPath.set(pickedPath);
    this.error.set(null);
  }

  normalizeId(value: string): string {
    return value.toLowerCase().replace(/[^a-z0-9_]/g, '');
  }

  addResearcher(): void {
    this.researchers.update((list) => [
      ...list,
      { email: '', name: '', assignment_percentage: 100, originalEmail: '' },
    ]);
  }

  removeResearcher(idx: number): void {
    this.researchers.update((list) => list.filter((_, i) => i !== idx));
  }

  saveResearchers(): void {
    this.error.set(null);
    this.saved.set(null);
    const rows = this.researchers().map((r) => ({
      email: r.email.trim().toLowerCase(),
      name: r.name.trim(),
      assignment_percentage: r.assignment_percentage ?? 100,
      originalEmail: r.originalEmail,
    }));
    if (rows.some((r) => !r.email || !r.name)) {
      this.error.set('Each researcher needs an email and a name.');
      return;
    }
    if (rows.some((r) => !EMAIL_RE.test(r.email))) {
      this.error.set('Each researcher email must contain @ and .');
      return;
    }
    const payload: ResearcherInput[] = rows.map((r) => ({
      email: r.email,
      name: r.name,
      assignment_percentage: r.assignment_percentage,
      ...(r.originalEmail && r.originalEmail !== r.email ? { previous_email: r.originalEmail } : {}),
    }));
    const previousToNext = new Map(
      rows
        .filter((r) => r.originalEmail)
        .map((r) => [r.originalEmail, r.email]),
    );
    this.api.replaceResearchers(payload).subscribe({
      next: (saved) => {
        const sorted = this.sortResearchers(saved);
        this.researchers.set(sorted.map((r) => ({ ...r, originalEmail: r.email, assignment_percentage: r.assignment_percentage ?? 100 })));
        this.projectSvc.project.update((project) => project ? { ...project, researchers: sorted } : project);
        const active = this.researcherSvc.activeId();
        if (active) {
          const nextActive = previousToNext.get(active) ?? active;
          if (!sorted.some((r) => r.email === nextActive)) {
            this.researcherSvc.set(null);
          } else if (nextActive !== active) {
            this.researcherSvc.set(nextActive);
          }
        }
        this.saved.set('Researchers saved.');
      },
      error: (e) => this.error.set(`Failed to save researchers: ${this.errorMessage(e)}`),
    });
  }

  addCriterion(): void {
    this.criteria.update((list) => [
      ...list,
      { id: '', kind: 'include', description: '', originalId: '' },
    ]);
  }

  removeCriterion(idx: number): void {
    this.criteria.update((list) => list.filter((_, i) => i !== idx));
  }

  saveCriteria(): void {
    this.error.set(null);
    this.saved.set(null);
    const rows = this.criteria().map((c) => ({
      id: this.normalizeId(c.id),
      kind: c.kind,
      description: c.description.trim(),
      originalId: c.originalId,
    }));
    if (rows.some((c) => !c.id || !c.description)) {
      this.error.set('Each criterion needs an id (letters/digits only) and a description.');
      return;
    }
    const payload: CriterionInput[] = rows.map((c) => ({
      id: c.id,
      kind: c.kind,
      description: c.description,
      ...(c.originalId && c.originalId !== c.id ? { previous_id: c.originalId } : {}),
    }));
    this.api.replaceCriteria(payload).subscribe({
      next: (saved) => {
        const sorted = this.sortCriteria(saved);
        this.criteria.set(sorted.map((c) => ({ ...c, originalId: c.id })));
        this.projectSvc.project.update((project) => project ? { ...project, criteria: sorted } : project);
        this.saved.set('Criteria saved.');
      },
      error: (e) => this.error.set(`Failed to save criteria: ${this.errorMessage(e)}`),
    });
  }

  addPhase(): void {
    this.phases.update((list) => [
      ...list,
      { id: '', description: '', originalId: '' },
    ]);
  }

  removePhase(idx: number): void {
    this.phases.update((list) => list.filter((_, i) => i !== idx));
  }

  savePhases(): void {
    this.error.set(null);
    this.saved.set(null);
    const rows = this.phases().map((p) => ({
      id: this.normalizeId(p.id),
      description: p.description.trim(),
      originalId: p.originalId,
    }));
    if (rows.some((p) => !p.id || !p.description)) {
      this.error.set('Each phase needs an id (letters/digits only) and a description.');
      return;
    }
    const payload: PhaseInput[] = rows.map((p) => ({
      id: p.id,
      description: p.description,
      ...(p.originalId && p.originalId !== p.id ? { previous_id: p.originalId } : {}),
    }));
    this.api.replacePhases(payload).subscribe({
      next: (saved) => {
        const sorted = this.sortPhases(saved);
        this.phases.set(sorted.map((p) => ({ ...p, originalId: p.id })));
        this.projectSvc.project.update((project) => project ? { ...project, phases: sorted } : project);
        this.saved.set('Phases saved.');
      },
      error: (e) => this.error.set(`Failed to save phases: ${this.errorMessage(e)}`),
    });
  }

  private sortResearcherRows(rows: ResearcherRow[]): ResearcherRow[] {
    return [...rows].sort((a, b) => a.name.localeCompare(b.name) || a.email.localeCompare(b.email));
  }

  private sortCriterionRows(rows: CriterionRow[]): CriterionRow[] {
    return [...rows].sort((a, b) => {
      const kindDiff = this.criterionOrder(a.kind) - this.criterionOrder(b.kind);
      return kindDiff || a.id.localeCompare(b.id);
    });
  }

  private sortPhaseRows(rows: PhaseRow[]): PhaseRow[] {
    return [...rows].sort((a, b) => a.id.localeCompare(b.id));
  }

  private sortResearchers(items: Researcher[]): Researcher[] {
    return [...items].sort((a, b) => a.name.localeCompare(b.name) || a.email.localeCompare(b.email));
  }

  private sortCriteria(items: Criterion[]): Criterion[] {
    return [...items].sort((a, b) => {
      const kindDiff = this.criterionOrder(a.kind) - this.criterionOrder(b.kind);
      return kindDiff || a.id.localeCompare(b.id);
    });
  }

  private sortPhases(items: Phase[]): Phase[] {
    return [...items].sort((a, b) => a.id.localeCompare(b.id));
  }

  private criterionOrder(kind: CriterionKind): number {
    return kind === 'include' ? 0 : 1;
  }

  private joinPath(base: string, leaf: string): string {
    return `${base.replace(/[\\/]+$/, '')}/${leaf}`;
  }

  private errorMessage(e: unknown): string {
    const err = e as { error?: { detail?: string }; message?: string };
    return err.error?.detail ?? err.message ?? 'unknown error';
  }
}
