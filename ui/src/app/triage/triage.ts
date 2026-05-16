import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../api.service';
import {
  Criterion,
  Decision,
  DecisionInput,
  Project,
  ReviewSet,
  Work,
} from '../models';
import { ResearcherService } from '../researcher.service';

@Component({
  selector: 'app-triage',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './triage.html',
  styleUrl: './triage.scss',
})
export class TriageComponent {
  private readonly api = inject(ApiService);
  private readonly researcherSvc = inject(ResearcherService);

  readonly project = signal<Project | null>(null);
  readonly sets = signal<ReviewSet[]>([]);
  readonly currentSet = signal<ReviewSet | null>(null);
  readonly decisions = signal<Decision[]>([]);
  readonly draft = signal<Record<string, DecisionInput>>({});
  readonly activeResearcherId = this.researcherSvc.activeId;
  readonly error = signal<string | null>(null);

  readonly showSelected = signal(true);
  readonly showRejected = signal(false);

  readonly filteredWorks = computed(() => {
    const set = this.currentSet();
    if (!set) return [];
    const showSel = this.showSelected();
    const showRej = this.showRejected();
    return set.works.filter((w) => {
      const verdict = this.decisionFor(w.id)?.verdict;
      if (!verdict) return true;
      if (verdict === 'accept') return showSel;
      return showRej;
    });
  });

  readonly includeCriteria = computed(
    () => this.project()?.criteria.filter((c) => c.kind === 'include') ?? [],
  );
  readonly excludeCriteria = computed(
    () => this.project()?.criteria.filter((c) => c.kind === 'exclude') ?? [],
  );

  constructor() {
    this.refresh();
  }

  refresh(): void {
    this.api.getProject().subscribe({
      next: (p) => this.project.set(p),
      error: (e) => this.error.set(`Failed to load project: ${e.message}`),
    });
    this.api.listSets().subscribe({
      next: (s) => {
        this.sets.set(s);
        if (s.length && !this.currentSet()) this.selectSet(s[0]);
      },
      error: (e) => this.error.set(`Failed to load sets: ${e.message}`),
    });
  }

  selectSet(s: ReviewSet): void {
    this.currentSet.set(s);
    this.api.getDecisions(s.id).subscribe({
      next: (r) => this.decisions.set(r.decisions),
      error: (e) => this.error.set(`Failed to load decisions: ${e.message}`),
    });
  }

  setResearcher(id: string): void {
    this.researcherSvc.set(id || null);
  }

  decisionFor(workId: string): Decision | undefined {
    const me = this.activeResearcherId();
    if (!me) return undefined;
    return this.decisions().find((d) => d.work_id === workId && d.researcher_id === me);
  }

  noteFor(workId: string): string {
    const draft = this.draft()[workId];
    if (draft && draft.note !== undefined) return draft.note ?? '';
    return this.decisionFor(workId)?.note ?? '';
  }

  updateNoteDraft(workId: string, note: string): void {
    this.draft.update((d) => ({ ...d, [workId]: { ...(d[workId] ?? {}), note } }));
  }

  onCriterionChange(work: Work, criterionId: string | null): void {
    const me = this.activeResearcherId();
    if (!me) {
      this.error.set('Select an active researcher first.');
      return;
    }
    const set = this.currentSet();
    if (!set) return;

    if (!criterionId) {
      this.api.deleteDecision(set.id, work.id).subscribe({
        next: () => {
          this.decisions.update((all) =>
            all.filter((d) => !(d.work_id === work.id && d.researcher_id === me)),
          );
          this.clearDraft(work.id);
          this.error.set(null);
        },
        error: (e) => this.error.set(`Failed to clear decision: ${e.message}`),
      });
      return;
    }

    const criterion = this.findCriterion(criterionId);
    if (!criterion) {
      this.error.set(`Unknown criterion: ${criterionId}`);
      return;
    }
    const body: DecisionInput = {
      verdict: criterion.kind === 'include' ? 'accept' : 'reject',
      criterion_id: criterion.id,
      note: this.noteFor(work.id) || null,
    };
    this.putDecision(set.id, work.id, body, me);
  }

  saveNote(work: Work): void {
    const me = this.activeResearcherId();
    if (!me) return;
    const set = this.currentSet();
    if (!set) return;
    const existing = this.decisionFor(work.id);
    if (!existing) return; // no decision yet → can't attach note
    const note = this.noteFor(work.id);
    if ((note || null) === (existing.note || null)) {
      this.clearDraft(work.id);
      return;
    }
    const body: DecisionInput = {
      verdict: existing.verdict,
      criterion_id: existing.criterion_id ?? null,
      note: note || null,
    };
    this.putDecision(set.id, work.id, body, me);
  }

  private putDecision(setId: string, workId: string, body: DecisionInput, me: string): void {
    this.api.upsertDecision(setId, workId, body).subscribe({
      next: (saved) => {
        this.decisions.update((all) => [
          ...all.filter((d) => !(d.work_id === workId && d.researcher_id === me)),
          saved,
        ]);
        this.clearDraft(workId);
        this.error.set(null);
      },
      error: (e) => this.error.set(`Failed to save decision: ${e.message}`),
    });
  }

  private clearDraft(workId: string): void {
    this.draft.update((d) => {
      const { [workId]: _, ...rest } = d;
      return rest;
    });
  }

  private findCriterion(id: string): Criterion | undefined {
    return this.project()?.criteria.find((c) => c.id === id);
  }

  trackById = (_: number, x: { id: string }) => x.id;
}
