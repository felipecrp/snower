import { CommonModule } from '@angular/common';
import { Component, HostListener, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { FontAwesomeModule } from '@fortawesome/angular-fontawesome';
import { faGear } from '@fortawesome/free-solid-svg-icons';

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

type SortField = 'author' | 'title' | 'venue' | 'criterion';
type CriterionDialog = { verdict: 'accept' | 'reject'; workId: string };
type VisibilityMode = 'pending' | 'selected' | 'rejected' | 'all' | 'custom';
type TriageCounts = { selected: number; rejected: number; total: number; shown: number };

const SORT_FIELDS: SortField[] = ['author', 'title', 'venue', 'criterion'];
const VISIBILITY_MODES: VisibilityMode[] = ['pending', 'selected', 'rejected', 'all'];

@Component({
  selector: 'app-triage',
  standalone: true,
  imports: [CommonModule, FontAwesomeModule, FormsModule, RouterLink],
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
  readonly sortField = signal<SortField>('author');
  readonly visibilityMode = signal<VisibilityMode>('selected');
  readonly selectedWorkId = signal<string | null>(null);
  readonly criterionDialog = signal<CriterionDialog | null>(null);
  readonly criterionQuery = signal('');
  readonly criterionNote = signal('');
  readonly highlightedCriterionIndex = signal(0);
  readonly lastCriterionByVerdict = signal<Partial<Record<'accept' | 'reject', string>>>({});
  readonly settingsIcon = faGear;

  readonly filteredWorks = computed(() => {
    const set = this.currentSet();
    if (!set) return [];
    const showSel = this.showSelected();
    const showRej = this.showRejected();
    const works = set.works.filter((w) => {
      const verdict = this.decisionFor(w.id)?.verdict;
      if (!verdict) return true;
      if (verdict === 'accept') return showSel;
      return showRej;
    });
    return this.sortWorks(works);
  });

  readonly includeCriteria = computed(
    () => this.project()?.criteria.filter((c) => c.kind === 'include') ?? [],
  );
  readonly excludeCriteria = computed(
    () => this.project()?.criteria.filter((c) => c.kind === 'exclude') ?? [],
  );
  readonly triageCounts = computed<TriageCounts>(() => {
    const set = this.currentSet();
    if (!set) return { selected: 0, rejected: 0, total: 0, shown: 0 };
    let selected = 0;
    let rejected = 0;
    for (const work of set.works) {
      const verdict = this.decisionFor(work.id)?.verdict;
      if (verdict === 'accept') selected += 1;
      if (verdict === 'reject') rejected += 1;
    }
    return {
      selected,
      rejected,
      total: set.works.length,
      shown: this.filteredWorks().length,
    };
  });
  readonly selectedWork = computed(() => {
    const works = this.filteredWorks();
    return works.find((w) => w.id === this.selectedWorkId()) ?? works[0] ?? null;
  });
  readonly dialogCriteria = computed(() => {
    const dialog = this.criterionDialog();
    if (!dialog) return [];
    const kind = dialog.verdict === 'accept' ? 'include' : 'exclude';
    const query = this.criterionQuery().trim();
    const criteria = this.project()?.criteria.filter((c) => c.kind === kind) ?? [];
    if (!query) return this.sortDialogCriteria(criteria, dialog.verdict);
    return criteria
      .map((criterion) => ({
        criterion,
        score: this.fuzzyScore(`${criterion.id} ${criterion.description}`, query),
      }))
      .filter((match) => match.score !== null)
      .sort((a, b) => a.score! - b.score! || this.compareCriterion(a.criterion, b.criterion))
      .map((match) => match.criterion);
  });

  constructor() {
    this.refresh();
  }

  refresh(): void {
    this.api.getProject().subscribe({
      next: (p) => {
        this.project.set(p);
        document.title = `Snow - ${p.name}`;
        const activeId = this.activeResearcherId();
        if (activeId && !p.researchers.some((r) => r.id === activeId)) {
          this.setResearcher(null);
        }
      },
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
    this.selectedWorkId.set(null);
    this.api.getDecisions(s.id).subscribe({
      next: (r) => this.decisions.set(r.decisions),
      error: (e) => this.error.set(`Failed to load decisions: ${e.message}`),
    });
  }

  startSnowballing(kind: 'backward' | 'forward'): void {
    this.api.runGlobalSnowballing(kind).subscribe({
      next: (created) => {
        this.sets.update((existing) => {
          const createdIds = new Set(created.map((s) => s.id));
          return [...existing.filter((s) => !createdIds.has(s.id)), ...created].sort((a, b) =>
            a.id.localeCompare(b.id),
          );
        });
        if (created.length) this.selectSet(created[created.length - 1]);
        this.error.set(null);
      },
      error: (e) => this.error.set(`Failed to run ${kind} snowballing: ${e.message}`),
    });
  }

  @HostListener('document:keydown', ['$event'])
  handleKeyboard(event: KeyboardEvent): void {
    if (this.criterionDialog()) return;
    if (this.isTypingTarget(event.target)) return;
    if (event.key === 'j') {
      event.preventDefault();
      this.moveSelection(1);
    } else if (event.key === 'k') {
      event.preventDefault();
      this.moveSelection(-1);
    } else if (event.key === 'a') {
      event.preventDefault();
      this.openCriterionDialog('accept');
    } else if (event.key === 'r') {
      event.preventDefault();
      this.openCriterionDialog('reject');
    } else if (event.key === 's') {
      event.preventDefault();
      this.cycleSortField();
    } else if (event.key === 't') {
      event.preventDefault();
      this.cycleVisibilityMode();
    }
  }

  setResearcher(id: string | null): void {
    this.researcherSvc.set(id || null);
  }

  setVisibilityMode(mode: VisibilityMode): void {
    this.visibilityMode.set(mode);
    this.showSelected.set(mode === 'selected' || mode === 'all');
    this.showRejected.set(mode === 'rejected' || mode === 'all');
  }

  decisionFor(workId: string): Decision | undefined {
    const me = this.activeResearcherId();
    if (!me) return undefined;
    return this.decisions().find((d) => d.work_id === workId && d.researcher_id === me);
  }

  voteCountsFor(workId: string): { selected: number; rejected: number } {
    let selected = 0;
    let rejected = 0;
    for (const decision of this.decisions()) {
      if (decision.work_id !== workId) continue;
      if (decision.verdict === 'accept') selected += 1;
      if (decision.verdict === 'reject') rejected += 1;
    }
    return { selected, rejected };
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
    this.rememberCriterion(body.verdict, criterion.id);
    this.putDecision(set.id, work.id, body, me, this.fallbackSelectionAfter(work.id));
  }

  selectWork(workId: string): void {
    this.selectedWorkId.set(workId);
  }

  isSelectedWork(workId: string): boolean {
    return this.selectedWork()?.id === workId;
  }

  openCriterionDialog(verdict: 'accept' | 'reject'): void {
    const me = this.activeResearcherId();
    if (!me) {
      this.error.set('Select an active researcher first.');
      return;
    }
    const work = this.selectedWork();
    if (!work) return;
    const criteria = verdict === 'accept' ? this.includeCriteria() : this.excludeCriteria();
    if (!criteria.length) {
      this.error.set(`No ${verdict === 'accept' ? 'include' : 'exclude'} criteria configured.`);
      return;
    }
    this.selectedWorkId.set(work.id);
    this.criterionDialog.set({ verdict, workId: work.id });
    this.criterionQuery.set('');
    this.criterionNote.set(this.noteFor(work.id));
    this.highlightedCriterionIndex.set(0);
    setTimeout(() => document.getElementById('criterion-search')?.focus());
  }

  closeCriterionDialog(): void {
    this.criterionDialog.set(null);
    this.criterionQuery.set('');
    this.criterionNote.set('');
    this.highlightedCriterionIndex.set(0);
  }

  updateCriterionQuery(query: string): void {
    this.criterionQuery.set(query);
    this.highlightedCriterionIndex.set(0);
  }

  updateCriterionNote(note: string): void {
    this.criterionNote.set(note);
  }

  moveHighlightedCriterion(delta: number): void {
    const criteria = this.dialogCriteria();
    if (!criteria.length) return;
    this.highlightedCriterionIndex.update((i) => (i + delta + criteria.length) % criteria.length);
  }

  confirmCriterionDialog(): void {
    const dialog = this.criterionDialog();
    const set = this.currentSet();
    const me = this.activeResearcherId();
    if (!dialog || !set || !me) return;
    const criteria = this.dialogCriteria();
    const criterion = criteria[this.highlightedCriterionIndex()] ?? criteria[0];
    if (!criterion) return;
    const body: DecisionInput = {
      verdict: dialog.verdict,
      criterion_id: criterion.id,
      note: this.criterionNote() || null,
    };
    this.rememberCriterion(dialog.verdict, criterion.id);
    this.putDecision(set.id, dialog.workId, body, me, this.fallbackSelectionAfter(dialog.workId));
    this.closeCriterionDialog();
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

  private putDecision(
    setId: string,
    workId: string,
    body: DecisionInput,
    me: string,
    fallbackWorkId: string | null = null,
  ): void {
    this.api.upsertDecision(setId, workId, body).subscribe({
      next: (saved) => {
        this.decisions.update((all) => [
          ...all.filter((d) => !(d.work_id === workId && d.researcher_id === me)),
          saved,
        ]);
        this.selectFallbackIfHidden(workId, fallbackWorkId);
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

  private fallbackSelectionAfter(workId: string): string | null {
    const works = this.filteredWorks();
    const index = works.findIndex((w) => w.id === workId);
    if (index < 0) return null;
    return works[index + 1]?.id ?? works[index - 1]?.id ?? null;
  }

  private selectFallbackIfHidden(workId: string, fallbackWorkId: string | null): void {
    if (this.filteredWorks().some((w) => w.id === workId)) return;
    if (!fallbackWorkId) {
      this.selectedWorkId.set(null);
      return;
    }
    this.selectedWorkId.set(fallbackWorkId);
    setTimeout(() => this.scrollToWork(fallbackWorkId));
  }

  private moveSelection(delta: number): void {
    const works = this.filteredWorks();
    if (!works.length) return;
    const currentId = this.selectedWork()?.id;
    const currentIndex = Math.max(0, works.findIndex((w) => w.id === currentId));
    const next = works[Math.min(Math.max(currentIndex + delta, 0), works.length - 1)];
    this.selectedWorkId.set(next.id);
    this.scrollToWork(next.id);
  }

  private cycleSortField(): void {
    const currentIndex = SORT_FIELDS.indexOf(this.sortField());
    this.sortField.set(SORT_FIELDS[(currentIndex + 1) % SORT_FIELDS.length]);
    setTimeout(() => {
      const work = this.selectedWork();
      if (work) this.scrollToWork(work.id);
    });
  }

  private cycleVisibilityMode(): void {
    const currentIndex = VISIBILITY_MODES.indexOf(this.visibilityMode());
    this.setVisibilityMode(VISIBILITY_MODES[(currentIndex + 1) % VISIBILITY_MODES.length]);
  }

  private rememberCriterion(verdict: 'accept' | 'reject', criterionId: string): void {
    this.lastCriterionByVerdict.update((last) => ({ ...last, [verdict]: criterionId }));
  }

  private sortDialogCriteria(criteria: Criterion[], verdict: 'accept' | 'reject'): Criterion[] {
    const lastCriterionId = this.lastCriterionByVerdict()[verdict];
    return [...criteria].sort((a, b) => {
      if (a.id === lastCriterionId) return -1;
      if (b.id === lastCriterionId) return 1;
      return this.compareCriterion(a, b);
    });
  }

  private compareCriterion(a: Criterion, b: Criterion): number {
    const description = this.compareSortValue(a.description, b.description);
    if (description !== 0) return description;
    return this.compareSortValue(a.id, b.id);
  }

  private fuzzyScore(value: string, query: string): number | null {
    const normalizedValue = value.toLocaleLowerCase();
    const normalizedQuery = query.toLocaleLowerCase();
    if (normalizedValue.includes(normalizedQuery)) return 0;
    let score = 0;
    let cursor = 0;
    for (const char of normalizedQuery) {
      const index = normalizedValue.indexOf(char, cursor);
      if (index === -1) return null;
      score += index - cursor + 1;
      cursor = index + 1;
    }
    return score;
  }

  private isTypingTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false;
    const tag = target.tagName.toLocaleLowerCase();
    return target.isContentEditable || tag === 'input' || tag === 'textarea' || tag === 'select';
  }

  private scrollToWork(workId: string): void {
    const work = document.getElementById(`work-${workId}`);
    const container = document.querySelector<HTMLElement>('.works');
    const filters = document.querySelector<HTMLElement>('.filters');
    if (!work || !container) return;
    const workRect = work.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const topEdge = filters?.getBoundingClientRect().bottom ?? containerRect.top;
    if (workRect.top < topEdge) {
      container.scrollBy({ top: workRect.top - topEdge - 12, behavior: 'smooth' });
    } else if (workRect.bottom > containerRect.bottom) {
      container.scrollBy({ top: workRect.bottom - containerRect.bottom + 12, behavior: 'smooth' });
    }
  }

  private sortWorks(works: Work[]): Work[] {
    const sortField = this.sortField();
    return [...works].sort((a, b) => {
      const bySelectedField = this.compareSortValue(
        this.sortValue(a, sortField),
        this.sortValue(b, sortField),
      );
      if (bySelectedField !== 0) return bySelectedField;
      return this.compareSortValue(this.sortValue(a, 'title'), this.sortValue(b, 'title'));
    });
  }

  private sortValue(work: Work, field: SortField): string {
    if (field === 'author') return work.authors[0] ?? '';
    if (field === 'title') return work.title;
    if (field === 'venue') return work.venue ?? '';
    const criterionId = this.decisionFor(work.id)?.criterion_id;
    if (!criterionId) return '';
    const criterion = this.findCriterion(criterionId);
    return criterion ? `${criterion.description} ${criterion.id}` : criterionId;
  }

  private compareSortValue(a: string, b: string): number {
    if (!a && b) return 1;
    if (a && !b) return -1;
    return a.localeCompare(b, undefined, { sensitivity: 'base' });
  }

  trackById = (_: number, x: { id: string }) => x.id;
}
