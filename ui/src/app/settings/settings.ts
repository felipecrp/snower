import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../api.service';
import {
  Criterion,
  CriterionInput,
  CriterionKind,
  Researcher,
  ResearcherInput,
} from '../models';

interface ResearcherRow extends Researcher {
  originalId: string;
}

interface CriterionRow extends Criterion {
  originalId: string;
}

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './settings.html',
  styleUrl: './settings.scss',
})
export class SettingsComponent {
  private readonly api = inject(ApiService);

  readonly researchers = signal<ResearcherRow[]>([]);
  readonly criteria = signal<CriterionRow[]>([]);
  readonly error = signal<string | null>(null);
  readonly saved = signal<string | null>(null);

  readonly criterionKinds: CriterionKind[] = ['include', 'exclude'];

  constructor() {
    this.refresh();
  }

  refresh(): void {
    this.api.getProject().subscribe({
      next: (p) => {
        this.researchers.set(p.researchers.map((r) => ({ ...r, originalId: r.id })));
        this.criteria.set(p.criteria.map((c) => ({ ...c, originalId: c.id })));
      },
      error: (e) => this.error.set(`Failed to load project: ${e.message}`),
    });
  }

  addResearcher(): void {
    this.researchers.update((list) => [
      ...list,
      { id: '', name: '', email: '', originalId: '' },
    ]);
  }

  removeResearcher(idx: number): void {
    this.researchers.update((list) => list.filter((_, i) => i !== idx));
  }

  saveResearchers(): void {
    this.error.set(null);
    this.saved.set(null);
    const rows = this.researchers().map((r) => ({
      id: r.id.trim(),
      name: r.name.trim(),
      email: r.email?.trim() || null,
      originalId: r.originalId,
    }));
    if (rows.some((r) => !r.id || !r.name)) {
      this.error.set('Each researcher needs an id and a name.');
      return;
    }
    const payload: ResearcherInput[] = rows.map((r) => ({
      id: r.id,
      name: r.name,
      email: r.email,
      ...(r.originalId && r.originalId !== r.id ? { previous_id: r.originalId } : {}),
    }));
    this.api.replaceResearchers(payload).subscribe({
      next: (saved) => {
        this.researchers.set(saved.map((r) => ({ ...r, originalId: r.id })));
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
      id: c.id.trim(),
      kind: c.kind,
      description: c.description.trim(),
      originalId: c.originalId,
    }));
    if (rows.some((c) => !c.id || !c.description)) {
      this.error.set('Each criterion needs an id and a description.');
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
        this.criteria.set(saved.map((c) => ({ ...c, originalId: c.id })));
        this.saved.set('Criteria saved.');
      },
      error: (e) => this.error.set(`Failed to save criteria: ${this.errorMessage(e)}`),
    });
  }

  private errorMessage(e: unknown): string {
    const err = e as { error?: { detail?: string }; message?: string };
    return err.error?.detail ?? err.message ?? 'unknown error';
  }
}
