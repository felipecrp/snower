import { CommonModule } from '@angular/common';
import { Component, HostListener, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../api.service';
import {
  Bidding,
  Criterion,
  Decision,
  DecisionInput,
  Phase,
  ReviewSet,
  Work,
} from '../models';
import { ProjectService } from '../project.service';
import { ResearcherService } from '../researcher.service';

type SortField = 'author' | 'title' | 'venue' | 'criterion';
type CriterionDialog = { verdict: 'accept' | 'reject'; bibId: string };
type VisibilityMode = 'pending' | 'selected' | 'rejected' | 'all' | 'custom';
type TriageCounts = { selected: number; rejected: number; total: number; shown: number };
type PendingWork = { work: Work; status: 'pending' | 'importing' | 'done' | 'error'; error?: string };

const SORT_FIELDS: SortField[] = ['author', 'title', 'venue', 'criterion'];

@Component({
  selector: 'app-snowballing',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './snowballing.html',
  styleUrl: './snowballing.scss',
})
export class SnowballingComponent {
  private readonly api = inject(ApiService);
  readonly projectSvc = inject(ProjectService);
  private readonly researcherSvc = inject(ResearcherService);

  readonly project = this.projectSvc.project;
  readonly sets = this.projectSvc.sets;
  readonly currentSet = signal<ReviewSet | null>(null);
  readonly decisions = signal<Decision[]>([]);
  readonly draft = signal<Record<string, DecisionInput>>({});
  readonly activeResearcherId = this.researcherSvc.activeId;
  readonly error = signal<string | null>(null);
  readonly importing = signal(false);
  readonly pendingWorks = signal<PendingWork[]>([]);
  readonly snowballRunning = signal(false);
  readonly snowballMenuOpen = signal(false);
  readonly inFlightSnowball = signal<ReadonlySet<string>>(new Set());

  readonly biddings = signal<Bidding[]>([]);
  readonly onlyAssigned = signal(false);
  readonly biddingRunning = signal(false);
  readonly resultsMode = signal(false);
  readonly showPending = signal(true);
  readonly showSelected = signal(true);
  readonly showRejected = signal(false);
  readonly sortField = signal<SortField>('author');
  readonly activePhase = signal<string | null>(null);
  readonly visibilityMode = signal<VisibilityMode>('selected');
  readonly selectedWorkId = signal<string | null>(null);
  readonly criterionDialog = signal<CriterionDialog | null>(null);
  readonly criterionQuery = signal('');
  readonly criterionNote = signal('');
  readonly highlightedCriterionIndex = signal(0);
  readonly lastCriterionByVerdict = signal<Partial<Record<'accept' | 'reject', string>>>({});
  readonly expandedWorkIds = signal<Record<string, boolean>>({});

  private pendingKeys = '';

  readonly assignedToMe = computed<Set<string>>(() => {
    const me = this.activeResearcherId();
    if (!me) return new Set();
    const bidding = this.biddings().find((b) => b.researcher_id === me);
    return new Set(bidding?.work_ids ?? []);
  });

  readonly filteredWorks = computed(() => {
    const set = this.currentSet();
    if (!set) return [];
    const showPend = this.showPending();
    const showSel = this.showSelected();
    const showRej = this.showRejected();
    const onlyAssigned = this.onlyAssigned();
    const assigned = this.assignedToMe();
    return this.sortWorks(
      set.works.filter((w) => {
        if (onlyAssigned && !assigned.has(w.bib_key)) return false;
        const verdict = this.decisionFor(w.bib_key)?.verdict;
        if (!verdict) return showPend;
        if (verdict === 'accept') return showSel;
        return showRej;
      }),
    );
  });

  readonly includeCriteria = computed(
    () => this.sortCriteria(this.project()?.criteria.filter((c) => c.kind === 'include') ?? []),
  );
  readonly excludeCriteria = computed(
    () => this.sortCriteria(this.project()?.criteria.filter((c) => c.kind === 'exclude') ?? []),
  );
  readonly phases = computed(() => this.project()?.phases ?? []);
  readonly triageCounts = computed<TriageCounts>(() => {
    const set = this.currentSet();
    if (!set) return { selected: 0, rejected: 0, total: 0, shown: 0 };
    let selected = 0;
    let rejected = 0;
    for (const work of set.works) {
      const verdict = this.decisionFor(work.bib_key)?.verdict;
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
    return works.find((w) => w.bib_key === this.selectedWorkId()) ?? works[0] ?? null;
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

  readonly regularSets = computed(() => this.sets().filter((s) => s.kind !== 'orphan'));
  readonly orphanSet = computed(() => this.sets().find((s) => s.kind === 'orphan') ?? null);
  readonly selectedAccepted = computed(() => {
    const w = this.selectedWork();
    return !!w && this.consensusFor(w.bib_key) === 'accept';
  });

  private static readonly LAST_SET_KEY = 'snow:last-set';
  private static readonly SHOW_PENDING_KEY = 'snow:show-pending';
  private static readonly SHOW_SELECTED_KEY = 'snow:show-selected';
  private static readonly SHOW_REJECTED_KEY = 'snow:show-rejected';
  private static readonly RESULTS_MODE_KEY = 'snow:results-mode';
  private static readonly SORT_FIELD_KEY = 'snow:sort-field';
  private static readonly ACTIVE_PHASE_KEY = 'snow:active-phase';
  private setAutoSelected = false;
  private lastFilteredWorkIds: string[] = [];

  constructor() {
    this.loadFilterPreferences();

    effect(() => {
      const sets = this.sets();
      if (!sets.length || this.setAutoSelected) return;
      this.setAutoSelected = true;
      const lastId = localStorage.getItem(SnowballingComponent.LAST_SET_KEY);
      const target =
        sets.find((s) => s.id === lastId) ??
        sets.find((s) => s.id === '00-start') ??
        sets[0];
      this.selectSet(target);
    });

    // Save filter preferences when they change
    effect(() => {
      localStorage.setItem(SnowballingComponent.SHOW_PENDING_KEY, String(this.showPending()));
      localStorage.setItem(SnowballingComponent.SHOW_SELECTED_KEY, String(this.showSelected()));
      localStorage.setItem(SnowballingComponent.SHOW_REJECTED_KEY, String(this.showRejected()));
      localStorage.setItem(SnowballingComponent.RESULTS_MODE_KEY, String(this.resultsMode()));
      localStorage.setItem(SnowballingComponent.SORT_FIELD_KEY, this.sortField());
      const ap = this.activePhase();
      if (ap !== null) {
        localStorage.setItem(SnowballingComponent.ACTIVE_PHASE_KEY, ap);
      } else {
        localStorage.removeItem(SnowballingComponent.ACTIVE_PHASE_KEY);
      }
    });

    // Auto-select first phase when phases load and none is selected or stored one is gone
    effect(() => {
      const phases = this.phases();
      if (!phases.length) return;
      const current = untracked(() => this.activePhase());
      if (!current || !phases.some((p) => p.id === current)) {
        this.activePhase.set(phases[0].id);
      }
    });

    // When filters/sort change, keep selected paper visible; if filtered out, pick previous
    // from the last visible list, else the next visible one from that same list order.
    effect(() => {
      const works = this.filteredWorks();
      const currentId = untracked(() => this.selectedWorkId());
      const visibleIds = works.map((w) => w.bib_key);
      const previousVisibleIds = untracked(() => this.lastFilteredWorkIds);

      if (!currentId || !works.length) {
        this.lastFilteredWorkIds = visibleIds;
        return;
      }
      if (visibleIds.includes(currentId)) {
        this.lastFilteredWorkIds = visibleIds;
        return;
      }

      const previousIndex = previousVisibleIds.indexOf(currentId);
      let nextId: string | undefined;

      if (previousIndex >= 0) {
        for (let i = previousIndex - 1; i >= 0; i -= 1) {
          if (visibleIds.includes(previousVisibleIds[i])) {
            nextId = previousVisibleIds[i];
            break;
          }
        }
        if (!nextId) {
          for (let i = previousIndex + 1; i < previousVisibleIds.length; i += 1) {
            if (visibleIds.includes(previousVisibleIds[i])) {
              nextId = previousVisibleIds[i];
              break;
            }
          }
        }
      }

      const fallbackId = nextId ?? visibleIds[0];
      this.selectedWorkId.set(fallbackId);
      this.lastFilteredWorkIds = visibleIds;
      setTimeout(() => this.scrollToWork(fallbackId));
    });
  }

  private loadFilterPreferences(): void {
    const showPending = localStorage.getItem(SnowballingComponent.SHOW_PENDING_KEY);
    if (showPending !== null) this.showPending.set(showPending === 'true');

    const showSelected = localStorage.getItem(SnowballingComponent.SHOW_SELECTED_KEY);
    if (showSelected !== null) this.showSelected.set(showSelected === 'true');

    const showRejected = localStorage.getItem(SnowballingComponent.SHOW_REJECTED_KEY);
    if (showRejected !== null) this.showRejected.set(showRejected === 'true');

    const resultsMode = localStorage.getItem(SnowballingComponent.RESULTS_MODE_KEY);
    if (resultsMode !== null) this.resultsMode.set(resultsMode === 'true');

    const sortField = localStorage.getItem(SnowballingComponent.SORT_FIELD_KEY);
    if (sortField && SORT_FIELDS.includes(sortField as SortField)) {
      this.sortField.set(sortField as SortField);
    }

    const activePhase = localStorage.getItem(SnowballingComponent.ACTIVE_PHASE_KEY);
    if (activePhase) this.activePhase.set(activePhase);
  }

  selectSet(s: ReviewSet): void {
    this.selectedWorkId.set(null);
    this.currentSet.set(s);
    localStorage.setItem(SnowballingComponent.LAST_SET_KEY, s.id);
    this.api.getBiddings(s.id).subscribe({
      next: (b) => this.biddings.set(b),
      error: () => this.biddings.set([]),
    });
    this.api.getDecisions(s.id).subscribe({
      next: (r) => {
        this.decisions.set(r.decisions);
        this.projectSvc.updateDecisionsForSet(s.id, r.decisions);
      },
      error: (e) => {
        if (e.status === 409) {
          this.projectSvc.bootstrapWorkspace();
          this.projectSvc.refresh();
          const currentSetId = this.currentSet()?.id;
          setTimeout(() => {
            if (currentSetId && this.currentSet()?.id === currentSetId) {
              this.selectSet(this.currentSet()!);
            }
          }, 500);
        } else {
          this.error.set(`Failed to load decisions: ${e.message}`);
        }
      },
    });
  }

  consensusCountFor(set: ReviewSet): { accepted: number; total: number } {
    const setDecisions = this.projectSvc.allDecisions()[set.id] ?? [];
    let accepted = 0;
    for (const work of set.works) {
      const votes = { selected: 0, rejected: 0 };
      for (const d of setDecisions) {
        if (d.bib_id !== work.bib_key) continue;
        if (d.verdict === 'accept') votes.selected++;
        else votes.rejected++;
      }
      if (votes.selected > votes.rejected) accepted++;
    }
    return { accepted, total: set.works.length };
  }

  @HostListener('document:keydown', ['$event'])
  handleKeyboard(event: KeyboardEvent): void {
    if (this.criterionDialog()) return;
    if (this.isTypingTarget(event.target)) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.shiftKey) {
      if (event.key === 'J') { event.preventDefault(); this.moveSetSelection(1); }
      else if (event.key === 'K') { event.preventDefault(); this.moveSetSelection(-1); }
      return;
    }
    if (this.pendingKeys === 'f') {
      this.pendingKeys = '';
      event.preventDefault();
      if (event.key === 'a') this.showSelected.update((v) => !v);
      else if (event.key === 'u') this.showPending.update((v) => !v);
      else if (event.key === 'r') this.showRejected.update((v) => !v);
      else if (event.key === 'f') this.resultsMode.update((v) => !v);
      else if (event.key === 's') this.cycleSortField();
      return;
    }

    if (this.pendingKeys === 'v') {
      this.pendingKeys = '';
      event.preventDefault();
      if (event.key === 'v') this.toggleSelectedWorkDetails();
      return;
    }

    if (this.pendingKeys === 'b') {
      this.pendingKeys = '';
      event.preventDefault();
      if (event.key === 'b') this.bidSelected();
      else if (event.key === 'u') this.unbidSelected();
      else if (event.key === 'a') this.runBidding();
      return;
    }

    if (this.pendingKeys === 'sf' || this.pendingKeys === 'sb') {
      const prev = this.pendingKeys;
      this.pendingKeys = '';
      event.preventDefault();
      const dir = prev[1] === 'f' ? 'forward' : 'backward';
      if (event.key === 's') this.runSnowballing(`${dir}-selected` as any);
      else if (event.key === 'a') this.runSnowballing(`${dir}-remaining` as any);
      return;
    }

    if (this.pendingKeys === 's') {
      if (event.key === 'f' || event.key === 'b') {
        this.pendingKeys = 's' + event.key;
        event.preventDefault();
        return;
      }
      if (event.key === 's') {
        this.pendingKeys = '';
        event.preventDefault();
        this.runSnowballingBoth('selected');
        return;
      }
      if (event.key === 'a') {
        this.pendingKeys = '';
        event.preventDefault();
        this.runSnowballingBoth('remaining');
        return;
      }
      this.pendingKeys = '';
    }

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
    } else if (event.key === 'u') {
      event.preventDefault();
      this.clearSelectedDecision();
    } else if (event.key === 'f') {
      event.preventDefault();
      this.pendingKeys = 'f';
    } else if (event.key === 's') {
      event.preventDefault();
      this.pendingKeys = 's';
    } else if (event.key === 'b') {
      event.preventDefault();
      this.pendingKeys = 'b';
    } else if (event.key === 'v') {
      event.preventDefault();
      this.pendingKeys = 'v';
    }
  }

  setVisibilityMode(mode: VisibilityMode): void {
    this.visibilityMode.set(mode);
    this.showSelected.set(mode === 'selected' || mode === 'all');
    this.showRejected.set(mode === 'rejected' || mode === 'all');
    this.releaseFilterFocus();
  }

  decisionFor(workId: string): Decision | undefined {
    const me = this.activeResearcherId();
    if (!me) return undefined;
    return this.decisions().find((d) => d.bib_id === workId && d.researcher_id === me);
  }

  consensusFor(workId: string): 'accept' | 'reject' | null {
    const { selected, rejected } = this.voteCountsFor(workId);
    if (selected > rejected) return 'accept';
    if (rejected > selected) return 'reject';
    return null;
  }

  voteCountsFor(workId: string): { selected: number; rejected: number } {
    let selected = 0;
    let rejected = 0;
    for (const decision of this.decisions()) {
      if (decision.bib_id !== workId) continue;
      if (decision.verdict === 'accept') selected += 1;
      if (decision.verdict === 'reject') rejected += 1;
    }
    return { selected, rejected };
  }

  commentCountFor(workId: string): number {
    return this.decisions().filter((decision) =>
      decision.bib_id === workId && !!decision.note?.trim(),
    ).length;
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
      this.api.deleteDecision(set.id, work.bib_key).subscribe({
        next: () => {
          this.decisions.update((all) =>
            all.filter((d) => !(d.bib_id === work.bib_key && d.researcher_id === me)),
          );
          this.clearDraft(work.bib_key);
          this.error.set(null);
          this.triggerOrphanRecalc();
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
      phase_id: this.activePhase(),
      note: this.noteFor(work.bib_key) || null,
    };
    this.rememberCriterion(body.verdict, criterion.id);
    this.putDecision(set.id, work.bib_key, body, me, this.fallbackSelectionAfter(work.bib_key));
  }

  private bidSelected(): void {
    const work = this.selectedWork();
    if (!work) {
      this.error.set('Select a paper first.');
      return;
    }
    const event = new Event('toggle-bid');
    this.toggleBid(event, work);
  }

  private unbidSelected(): void {
    const work = this.selectedWork();
    if (!work) {
      this.error.set('Select a paper first.');
      return;
    }
    const me = this.activeResearcherId();
    if (!me) {
      this.error.set('Select an active researcher first.');
      return;
    }
    const set = this.currentSet();
    if (!set) return;
    if (!this.isBidded(work.bib_key)) {
      this.error.set('Paper is not bidded.');
      return;
    }
    this.api.removeBid(set.id, work.bib_key).subscribe({
      next: (updated) => {
        this.biddings.update((all) => {
          const without = all.filter((b) => b.researcher_id !== me);
          return [...without, updated];
        });
      },
      error: (e) => this.error.set(`Failed to remove bid: ${e.message}`),
    });
  }

  private runSnowballingBoth(kind: 'selected' | 'remaining'): void {
    const selectedKind = kind === 'selected' ? 'backward-selected' : 'backward-remaining';
    this.runSnowballing(selectedKind as any);
    setTimeout(() => {
      const forwardKind = kind === 'selected' ? 'forward-selected' : 'forward-remaining';
      this.runSnowballing(forwardKind as any);
    }, 100);
  }

  runSnowballing(kind: 'both-remaining' | 'backward-remaining' | 'forward-remaining' | 'backward-selected' | 'forward-selected'): void {
    this.snowballMenuOpen.set(false);
    this.error.set(null);

    if (kind === 'backward-selected' || kind === 'forward-selected') {
      const work = this.selectedWork();
      if (!work) { this.error.set('Select a paper first.'); return; }
      if (this.consensusFor(work.bib_key) !== 'accept') {
        this.error.set('Snowballing is only available for consensus-accepted papers.');
        return;
      }
      this.snowballRunning.set(true);
      const direction = kind === 'backward-selected' ? 'backward' : 'forward';
      const sourceSet = this.currentSet();
      const targetId = sourceSet
        ? `${(sourceSet.iteration + 1).toString().padStart(2, '0')}-${direction}`
        : null;
      this.applyOptimisticSnowball(work, direction);
      const pending: string[] = [];
      if (targetId) {
        this.projectSvc.ensurePlaceholderSet(targetId, direction, (sourceSet?.iteration ?? 0) + 1);
        this.projectSvc.markSetsPending([targetId]);
        pending.push(targetId);
      }
      this.api.runPaperSnowballing(direction, work.bib_key).subscribe({
        next: (updatedSets) => {
          this.snowballRunning.set(false);
          this.syncSetsAfterSnowballing(updatedSets);
          this.projectSvc.clearSetsPending(pending);
          this.clearInFlightSnowball(work, direction);
        },
        error: (e) => {
          this.error.set(`Snowballing failed: ${e.error?.detail ?? e.message}`);
          this.snowballRunning.set(false);
          this.projectSvc.clearSetsPending(pending);
          this.clearInFlightSnowball(work, direction);
        },
      });
      return;
    }

    this.snowballRunning.set(true);
    const directions: Array<'backward' | 'forward'> =
      kind === 'both-remaining' ? ['backward', 'forward'] : [kind.split('-')[0] as 'backward' | 'forward'];

    const pendingGlobal = this.sets()
      .filter((s) => directions.includes(s.kind as 'backward' | 'forward'))
      .map((s) => s.id);
    this.projectSvc.markSetsPending(pendingGlobal);

    const runNext = (accumulated: ReviewSet[], remaining: typeof directions) => {
      if (!remaining.length) {
        this.snowballRunning.set(false);
        this.syncSetsAfterSnowballing(accumulated);
        this.projectSvc.clearSetsPending(pendingGlobal);
        return;
      }
      const [head, ...tail] = remaining;
      this.api.runGlobalSnowballing(head).subscribe({
        next: (updatedSets) => runNext([...accumulated, ...updatedSets], tail),
        error: (e) => {
          this.error.set(`Snowballing failed: ${e.error?.detail ?? e.message}`);
          this.snowballRunning.set(false);
          this.projectSvc.clearSetsPending(pendingGlobal);
        },
      });
    };

    runNext([], directions);
  }

  private applyOptimisticSnowball(work: Work, direction: 'backward' | 'forward'): void {
    const timestamp = new Date().toISOString();
    const field = direction === 'backward'
      ? 'last_backward_snowballed_at'
      : 'last_forward_snowballed_at';
    const updater = (w: Work) =>
      w.bib_key === work.bib_key ? { ...w, [field]: timestamp } as Work : w;
    this.currentSet.update((cs) => cs ? { ...cs, works: cs.works.map(updater) } : cs);
    this.projectSvc.sets.update((all) =>
      all.map((s) => ({ ...s, works: s.works.map(updater) })),
    );
    const key = `${direction}:${work.bib_key}`;
    this.inFlightSnowball.update((set) => new Set(set).add(key));
  }

  clearInFlightSnowball(work: Work, direction: 'backward' | 'forward'): void {
    const key = `${direction}:${work.bib_key}`;
    this.inFlightSnowball.update((set) => {
      const next = new Set(set);
      next.delete(key);
      return next;
    });
  }

  isSnowballInFlight(work: Work, direction: 'backward' | 'forward'): boolean {
    return this.inFlightSnowball().has(`${direction}:${work.bib_key}`);
  }

  private syncSetsAfterSnowballing(updatedSets: ReviewSet[]): void {
    if (!updatedSets.length) return;
    this.projectSvc.sets.update((all) => {
      const byId = new Map(updatedSets.map((s) => [s.id, s]));
      return all.map((s) => byId.get(s.id) ?? s).concat(
        updatedSets.filter((s) => !all.some((a) => a.id === s.id))
      );
    });
    const current = this.currentSet();
    if (current) {
      const refreshed = updatedSets.find((s) => s.id === current.id);
      if (refreshed) {
        this.currentSet.set(refreshed);
      } else {
        this.api.getSet(current.id).subscribe({
          next: (freshSet) => {
            this.currentSet.set(freshSet);
            this.projectSvc.sets.update((all) =>
              all.map((s) => s.id === freshSet.id ? freshSet : s)
            );
          },
        });
      }
    }
  }

  isBidded(workId: string): boolean {
    return this.assignedToMe().has(workId);
  }

  toggleBid(event: Event, work: Work): void {
    event.stopPropagation();
    const me = this.activeResearcherId();
    if (!me) { this.error.set('Select an active researcher first.'); return; }
    const set = this.currentSet();
    if (!set) return;
    const bidded = this.isBidded(work.bib_key);
    const call$ = bidded
      ? this.api.removeBid(set.id, work.bib_key)
      : this.api.addBid(set.id, work.bib_key);
    call$.subscribe({
      next: (updated) => {
        this.biddings.update((all) => {
          const without = all.filter((b) => b.researcher_id !== me);
          return [...without, updated];
        });
      },
      error: (e) => this.error.set(`Failed to update bid: ${e.message}`),
    });
  }

  assignedInitials(workId: string): string[] {
    const project = this.project();
    if (!project) return [];
    const byEmail = new Map(project.researchers.map((r) => [r.email, r.name]));
    return this.biddings()
      .filter((b) => b.work_ids.includes(workId))
      .map((b) => {
        const name = byEmail.get(b.researcher_id) ?? b.researcher_id;
        return name.split(/\s+/).map((w) => w[0]?.toUpperCase() ?? '').join('').slice(0, 2);
      });
  }

  runBidding(): void {
    this.error.set(null);
    this.biddingRunning.set(true);
    this.api.runBidding().subscribe({
      next: () => {
        this.biddingRunning.set(false);
        this.error.set(null);
        const setId = this.currentSet()?.id;
        if (setId) {
          this.api.getBiddings(setId).subscribe({
            next: (b) => this.biddings.set(b),
            error: () => this.biddings.set([]),
          });
        }
      },
      error: (e) => {
        this.biddingRunning.set(false);
        this.error.set(`Bidding failed: ${e.error?.detail ?? e.message}`);
      },
    });
  }

  triggerBibImport(): void {
    document.getElementById('bib-import-input')?.click();
  }

  onBibFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.importing.set(true);
    this.error.set(null);
    this.pendingWorks.set([]);
    input.value = '';

    this.projectSvc.markSetsPending(['00-start']);
    const startSet = this.projectSvc.sets().find((s) => s.id === '00-start');
    if (startSet && this.currentSet()?.id !== '00-start') {
      this.selectSet(startSet);
    }
    this.api.parseBib('00-start', file).subscribe({
      next: (works) => {
        this.pendingWorks.set(works.map((w) => ({ work: w, status: 'pending' })));
        this.importNextWork(0);
      },
      error: (e) => {
        this.error.set(`Parse failed: ${e.error?.detail ?? e.message}`);
        this.importing.set(false);
        this.projectSvc.clearSetsPending(['00-start']);
      },
    });
  }

  private importNextWork(index: number): void {
    const pending = this.pendingWorks();
    if (index >= pending.length) {
      this.api.getSet('00-start').subscribe({
        next: (updatedSet) => {
          this.projectSvc.sets.update((all) =>
            all.map((s) => (s.id === '00-start' ? updatedSet : s)),
          );
          this.importing.set(false);
          this.projectSvc.clearSetsPending(['00-start']);
          this.pendingWorks.set([]);
          this.selectSet(updatedSet);
        },
        error: () => {
          this.importing.set(false);
          this.projectSvc.clearSetsPending(['00-start']);
          this.pendingWorks.set([]);
        },
      });
      return;
    }

    this.pendingWorks.update((all) =>
      all.map((item, i) => (i === index ? { ...item, status: 'importing' } : item)),
    );

    this.api.importWork('00-start', pending[index].work).subscribe({
      next: (importedWork) => {
        const mergeWork = (works: Work[]): Work[] => {
          const idx = works.findIndex((w) => w.bib_key === importedWork.bib_key);
          return idx >= 0
            ? works.map((w, i) => (i === idx ? importedWork : w))
            : [...works, importedWork];
        };
        this.projectSvc.sets.update((all) =>
          all.map((s) => (s.id === '00-start' ? { ...s, works: mergeWork(s.works) } : s)),
        );
        this.currentSet.update((cs) =>
          cs && cs.id === '00-start' ? { ...cs, works: mergeWork(cs.works) } : cs,
        );
        this.pendingWorks.update((all) =>
          all.map((item, i) => (i === index ? { ...item, status: 'done' } : item)),
        );
        this.importNextWork(index + 1);
      },
      error: (e) => {
        this.pendingWorks.update((all) =>
          all.map((item, i) =>
            i === index
              ? { ...item, status: 'error', error: e.error?.detail ?? e.message }
              : item,
          ),
        );
        this.importNextWork(index + 1);
      },
    });
  }

  selectWork(workId: string): void {
    this.selectedWorkId.set(workId);
  }

  isSelectedWork(workId: string): boolean {
    return this.selectedWork()?.bib_key === workId;
  }

  isWorkExpanded(workId: string): boolean {
    return !!this.expandedWorkIds()[workId];
  }

  toggleWorkDetails(workId: string): void {
    this.expandedWorkIds.update((expanded) => ({
      ...expanded,
      [workId]: !expanded[workId],
    }));
  }

  toggleSelectedWorkDetails(): void {
    const work = this.selectedWork();
    if (!work) return;
    this.toggleWorkDetails(work.bib_key);
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
    this.selectedWorkId.set(work.bib_key);
    this.criterionDialog.set({ verdict, bibId: work.bib_key });
    this.criterionQuery.set('');
    this.criterionNote.set(this.noteFor(work.bib_key));
    this.highlightedCriterionIndex.set(0);
    setTimeout(() => document.getElementById('criterion-search')?.focus());
  }

  closeCriterionDialog(): void {
    this.criterionDialog.set(null);
    this.criterionQuery.set('');
    this.criterionNote.set('');
    this.highlightedCriterionIndex.set(0);
  }

  getActivePhaseInfo(): Phase | null {
    const phaseId = this.activePhase();
    if (!phaseId) return null;
    return this.phases().find((p) => p.id === phaseId) ?? null;
  }

  getPhaseInfoForWork(workId: string): Phase | null {
    const decision = this.decisionFor(workId);
    if (!decision?.phase_id) return null;
    return this.phases().find((p) => p.id === decision.phase_id) ?? null;
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
      phase_id: this.activePhase(),
      note: this.criterionNote() || null,
    };
    this.rememberCriterion(dialog.verdict, criterion.id);
    this.putDecision(set.id, dialog.bibId, body, me, this.fallbackSelectionAfter(dialog.bibId));
    this.closeCriterionDialog();
  }

  onPhaseAssign(work: Work, phaseId: string | null): void {
    const me = this.activeResearcherId();
    if (!me) {
      this.error.set('Select an active researcher first.');
      return;
    }
    const set = this.currentSet();
    if (!set) return;
    const existing = this.decisionFor(work.bib_key);
    if (!existing) return;
    const body: DecisionInput = {
      verdict: existing.verdict,
      criterion_id: existing.criterion_id ?? null,
      phase_id: phaseId,
      note: this.noteFor(work.bib_key) || null,
    };
    this.putDecision(set.id, work.bib_key, body, me);
  }

  saveNote(work: Work): void {
    const me = this.activeResearcherId();
    if (!me) return;
    const set = this.currentSet();
    if (!set) return;
    const existing = this.decisionFor(work.bib_key);
    if (!existing) return;
    const note = this.noteFor(work.bib_key);
    if ((note || null) === (existing.note || null)) {
      this.clearDraft(work.bib_key);
      return;
    }
    const body: DecisionInput = {
      verdict: existing.verdict,
      criterion_id: existing.criterion_id ?? null,
      phase_id: existing.phase_id ?? null,
      note: note || null,
    };
    this.putDecision(set.id, work.bib_key, body, me);
  }

  blurAndSaveNote(event: Event, work: Work): void {
    this.saveNote(work);
    if (event.target instanceof HTMLElement) {
      event.target.blur();
    }
  }

  private putDecision(
    setId: string,
    bibId: string,
    body: DecisionInput,
    me: string,
    fallbackWorkId: string | null = null,
  ): void {
    this.api.upsertDecision(setId, bibId, body).subscribe({
      next: (saved) => {
        this.decisions.update((all) => [
          ...all.filter((d) => !(d.bib_id === bibId && d.researcher_id === me)),
          saved,
        ]);
        this.selectFallbackIfHidden(bibId, fallbackWorkId);
        this.clearDraft(bibId);
        this.error.set(null);
        this.triggerOrphanRecalc();
      },
      error: (e) => this.error.set(`Failed to save decision: ${e.message}`),
    });
  }

  private orphanRecalcInFlight = false;
  private orphanRecalcPending = false;

  private triggerOrphanRecalc(): void {
    if (this.orphanRecalcInFlight) {
      this.orphanRecalcPending = true;
      return;
    }
    this.startOrphanRecalc();
  }

  private startOrphanRecalc(): void {
    this.orphanRecalcInFlight = true;
    const affected = this.sets()
      .filter((s) => s.kind === 'backward' || s.kind === 'forward' || s.kind === 'orphan')
      .map((s) => s.id);
    this.projectSvc.markSetsPending([...affected, 'orphan']);
    this.api.recalculateOrphans().subscribe({
      next: (sets) => this.finishOrphanRecalc(sets, affected),
      error: (e) => {
        this.error.set(`Failed to recalculate orphans: ${e.message}`);
        this.projectSvc.clearSetsPending([...affected, 'orphan']);
        this.orphanRecalcInFlight = false;
      },
    });
  }

  private finishOrphanRecalc(sets: ReviewSet[], affected: string[]): void {
    this.projectSvc.sets.set(sets);
    const cs = this.currentSet();
    if (cs) {
      const updated = sets.find((s) => s.id === cs.id);
      if (updated) this.currentSet.set(updated);
    }
    this.projectSvc.clearSetsPending([...affected, 'orphan']);
    this.orphanRecalcInFlight = false;
    if (this.orphanRecalcPending) {
      this.orphanRecalcPending = false;
      this.startOrphanRecalc();
    }
  }

  private clearDraft(workId: string): void {
    this.draft.update((d) => {
      const { [workId]: _, ...rest } = d;
      return rest;
    });
  }

  private clearSelectedDecision(): void {
    const work = this.selectedWork();
    if (!work) return;
    this.onCriterionChange(work, null);
  }

  private findCriterion(id: string): Criterion | undefined {
    return this.project()?.criteria.find((c) => c.id === id);
  }

  private fallbackSelectionAfter(workId: string): string | null {
    const works = this.filteredWorks();
    const index = works.findIndex((w) => w.bib_key === workId);
    if (index < 0) return null;
    return works[index + 1]?.bib_key ?? works[index - 1]?.bib_key ?? null;
  }

  private selectFallbackIfHidden(workId: string, fallbackWorkId: string | null): void {
    if (this.filteredWorks().some((w) => w.bib_key === workId)) return;
    if (!fallbackWorkId) {
      this.selectedWorkId.set(null);
      return;
    }
    this.selectedWorkId.set(fallbackWorkId);
    setTimeout(() => this.scrollToWork(fallbackWorkId));
  }

  private moveSetSelection(delta: number): void {
    const sets = this.sets();
    if (!sets.length) return;
    const currentId = this.currentSet()?.id;
    const currentIndex = Math.max(0, sets.findIndex((s) => s.id === currentId));
    const next = sets[Math.min(Math.max(currentIndex + delta, 0), sets.length - 1)];
    this.selectSet(next);
  }

  private moveSelection(delta: number): void {
    const works = this.filteredWorks();
    if (!works.length) return;
    const currentId = this.selectedWork()?.bib_key;
    const currentIndex = Math.max(0, works.findIndex((w) => w.bib_key === currentId));
    const next = works[Math.min(Math.max(currentIndex + delta, 0), works.length - 1)];
    this.selectedWorkId.set(next.bib_key);
    this.scrollToWork(next.bib_key);
  }

  private cycleSortField(): void {
    const currentIndex = SORT_FIELDS.indexOf(this.sortField());
    this.sortField.set(SORT_FIELDS[(currentIndex + 1) % SORT_FIELDS.length]);
    setTimeout(() => {
      const work = this.selectedWork();
      if (work) this.scrollToWork(work.bib_key);
    });
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
    return this.compareSortValue(a.id, b.id);
  }

  private sortCriteria(criteria: Criterion[]): Criterion[] {
    return [...criteria].sort((a, b) => this.compareCriterion(a, b));
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
    return target.isContentEditable || tag === 'textarea' || this.isTextEntryControl(target);
  }

  private isTextEntryControl(target: HTMLElement): boolean {
    if (target.tagName.toLocaleLowerCase() === 'select') return true;
    if (target.tagName.toLocaleLowerCase() !== 'input') return false;
    const input = target as HTMLInputElement;
    return !['checkbox', 'radio', 'button', 'submit', 'reset'].includes(input.type);
  }

  releaseFilterFocus(): void {
    setTimeout(() => {
      const active = document.activeElement;
      if (active instanceof HTMLElement) active.blur();
    });
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
    const criterionId = this.decisionFor(work.bib_key)?.criterion_id;
    if (!criterionId) return '';
    const criterion = this.findCriterion(criterionId);
    return criterion ? `${criterion.description} ${criterion.id}` : criterionId;
  }

  private compareSortValue(a: string, b: string): number {
    if (!a && b) return 1;
    if (a && !b) return -1;
    return a.localeCompare(b, undefined, { sensitivity: 'base' });
  }

  formatSetTitle(id: string, kind: string): string {
    const match = id.match(/^(\d+)-(.+)$/);
    if (!match) return id;
    const [, num, slug] = match;
    const word = slug.charAt(0).toUpperCase() + slug.slice(1);
    const kindLabel = kind === 'start' ? 'Set' : '';
    return `${num} ${word}${kindLabel ? ' ' + kindLabel : ''}`.trim();
  }

  hasPaperLinks(work: Work): boolean {
    return !!(work.url || work.pdf_url || work.doi);
  }

  localPdfUrl(bib_key: string): string {
    return this.api.localPdfUrl(bib_key);
  }

  trackBySetId = (_: number, x: ReviewSet) => x.id;
  trackByBibKey = (_: number, x: Work) => x.bib_key;
  trackByCriterionId = (_: number, x: Criterion) => x.id;
}
