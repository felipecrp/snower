import { Component, OnInit, computed, effect, inject, signal, untracked } from '@angular/core';

import {
  Assessment,
  AssessmentMap,
  Criterion,
  Paper,
  Phase,
  SetSummary,
  isIncluded,
  setKey,
} from '../../models/snower.models';
import { SessionService } from '../../services/session.service';
import { SnowerService } from '../../services/snower.service';

/**
 * Snowballing page — browse derived sets and record screening assessments.
 *
 * Left pane lists all sets; selecting one loads its papers on the right.
 * Each paper shows phase + criterion dropdowns. When both are chosen and a
 * researcher is selected in the top bar, the assessment is auto-submitted.
 * The paper's existing assessments are shown below.
 */
@Component({
  selector: 'app-snowballing',
  templateUrl: './snowballing.html',
})
export class SnowballingPage implements OnInit {
  private readonly snower = inject(SnowerService);
  protected readonly session = inject(SessionService);

  protected readonly loadingSets = signal(true);
  protected readonly setsError = signal<string | null>(null);
  protected readonly sets = signal<SetSummary[]>([]);

  protected readonly sortedSets = computed(() => {
    const all = this.sets();
    return [...all].sort((a, b) => {
      if (a.name === 'orphans' && b.name !== 'orphans') return 1;
      if (b.name === 'orphans' && a.name !== 'orphans') return -1;
      return 0;
    });
  });

  protected readonly selectedSet = signal<SetSummary | null>(null);
  protected readonly loadingPapers = signal(false);
  protected readonly papersError = signal<string | null>(null);
  protected readonly papers = signal<Paper[]>([]);

  protected readonly criteria = signal<Criterion[]>([]);
  protected readonly phases = signal<Phase[]>([]);

  /** Per-paper assessment maps loaded from API or returned by assessPaper. */
  protected readonly assessmentMaps = signal<Record<string, AssessmentMap>>({});

  /** Draft phase selection per paper (bib_id → phase_id). */
  protected readonly draftPhase = signal<Record<string, string>>({});
  /** Draft criterion selection per paper (bib_id → criterion_id). */
  protected readonly draftCriterion = signal<Record<string, string>>({});
  /** Draft comment per paper (bib_id → comment text). */
  protected readonly draftComment = signal<Record<string, string>>({});

  protected readonly sortBy = signal<'title' | 'author'>('title');

  protected readonly showVotes = signal(false);
  protected readonly showDecision = signal(false);

  protected readonly filterMyIncluded = signal(true);
  protected readonly filterMyExcluded = signal(true);
  protected readonly filterMyUndecided = signal(true);

  protected readonly filterDecisionIncluded = signal(true);
  protected readonly filterDecisionExcluded = signal(true);
  protected readonly filterDecisionUndecided = signal(true);

  protected readonly filteredPapers = computed(() => {
    const papers = this.papers();
    const email = this.session.currentResearcherEmail();
    const maps = this.assessmentMaps();

    const fmi = this.filterMyIncluded();
    const fme = this.filterMyExcluded();
    const fmu = this.filterMyUndecided();

    const fdi = this.filterDecisionIncluded();
    const fde = this.filterDecisionExcluded();
    const fdu = this.filterDecisionUndecided();

    const sortBy = this.sortBy();

    const sorted = [...papers].sort((a, b) => {
      if (sortBy === 'author') {
        const aFamily = a.authors?.[0]?.family ?? '';
        const bFamily = b.authors?.[0]?.family ?? '';
        return aFamily.localeCompare(bFamily);
      }
      return (a.title ?? '').localeCompare(b.title ?? '');
    });

    return sorted.filter((p) => {
      const decision = p.decision ?? 'undecided';
      const passesDecision =
        (fdi && decision === 'included') ||
        (fde && decision === 'excluded') ||
        (fdu && decision === 'undecided');

      let myStatus: 'included' | 'excluded' | 'undecided';
      if (email && p.bib_id && maps[p.bib_id]?.[email]) {
        myStatus = isIncluded(maps[p.bib_id][email]) ? 'included' : 'excluded';
      } else {
        myStatus = 'undecided';
      }
      const passesMyReview =
        (fmi && myStatus === 'included') ||
        (fme && myStatus === 'excluded') ||
        (fmu && myStatus === 'undecided');

      return passesDecision && passesMyReview;
    });
  });

  protected readonly setKey = setKey;
  protected readonly isIncluded = isIncluded;

  constructor() {
    effect(() => {
      const email = this.session.currentResearcherEmail();
      const papers = this.papers();
      const assessmentMaps = this.assessmentMaps();

      const newDraftPhase: Record<string, string> = {};
      const newDraftCriterion: Record<string, string> = {};
      const newDraftComment: Record<string, string> = {};

      if (email) {
        for (const paper of papers) {
          if (!paper.bib_id) continue;
          const existing = assessmentMaps[paper.bib_id]?.[email];
          if (existing) {
            newDraftPhase[paper.bib_id] = existing.phase.id;
            newDraftCriterion[paper.bib_id] = existing.criterion.id;
            if (existing.comment) newDraftComment[paper.bib_id] = existing.comment;
          }
        }
      }

      untracked(() => {
        this.draftPhase.set(newDraftPhase);
        this.draftCriterion.set(newDraftCriterion);
        this.draftComment.set(newDraftComment);
      });
    });
  }

  protected setLabel(set: SetSummary): string {
    if (set.name === 'start_set') return 'Start Set';
    if (set.name === 'orphans') return 'Orphans';
    return `${set.name} · round ${set.round}`;
  }

  ngOnInit(): void {
    this.loadSets();
    this.snower.getCriteria().subscribe({ next: (d) => this.criteria.set(d), error: () => {} });
    this.snower.getPhases().subscribe({ next: (d) => this.phases.set(d), error: () => {} });
    this.session.refreshResearchers();
  }

  private loadSets(): void {
    this.snower.getSets().subscribe({
      next: (data) => {
        this.sets.set(data);
        this.loadingSets.set(false);
        if (this.selectedSet() === null && this.sortedSets().length > 0) {
          this.selectSet(this.sortedSets()[0]);
        }
      },
      error: (err) => {
        this.setsError.set(err?.message ?? 'Failed to load sets');
        this.loadingSets.set(false);
      },
    });
  }

  protected selectSet(set: SetSummary): void {
    this.selectedSet.set(set);
    this.loadPapers(setKey(set));
  }

  private loadPapers(key: string): void {
    this.loadingPapers.set(true);
    this.papersError.set(null);

    this.snower.getPapersInSet(key).subscribe({
      next: (papers) => {
        this.papers.set(papers);
        this.loadingPapers.set(false);
        const maps: Record<string, AssessmentMap> = {};
        for (const p of papers) {
          if (p.bib_id) maps[p.bib_id] = p.assessments ?? {};
        }
        this.assessmentMaps.set(maps);
      },
      error: (err) => {
        this.papersError.set(err?.message ?? 'Failed to load papers');
        this.loadingPapers.set(false);
      },
    });
  }

  protected onPhaseChange(paper: Paper, event: Event): void {
    if (!paper.bib_id) return;
    const value = (event.target as HTMLSelectElement).value;
    this.draftPhase.update((m) => ({ ...m, [paper.bib_id!]: value }));
    this.maybeAssess(paper);
  }

  protected onCriterionChange(paper: Paper, event: Event): void {
    if (!paper.bib_id) return;
    const value = (event.target as HTMLSelectElement).value;
    this.draftCriterion.update((m) => ({ ...m, [paper.bib_id!]: value }));
    if (!value) {
      this.maybeRemoveAssessment(paper);
    } else {
      this.maybeAssess(paper);
    }
  }

  protected onCommentChange(paper: Paper, event: Event): void {
    if (!paper.bib_id) return;
    const value = (event.target as HTMLInputElement).value;
    this.draftComment.update((m) => ({ ...m, [paper.bib_id!]: value }));
  }

  protected onCommentBlur(paper: Paper): void {
    this.maybeAssess(paper);
  }

  private maybeRemoveAssessment(paper: Paper): void {
    if (!paper.bib_id) return;
    const id = paper.bib_id;
    const researcher_email = this.session.currentResearcherEmail();
    if (!researcher_email) return;
    if (!this.assessmentMaps()[id]?.[researcher_email]) return;

    this.snower.removeAssessment(id, researcher_email).subscribe({
      next: (updated) => {
        this.papers.update((list) => list.map((p) => (p.bib_id === id ? { ...p, decision: updated.decision } : p)));
        this.assessmentMaps.update((all) => ({ ...all, [id]: updated.assessments ?? {} }));
        this.draftPhase.update((m) => { const n = { ...m }; delete n[id]; return n; });
        this.draftCriterion.update((m) => { const n = { ...m }; delete n[id]; return n; });
        this.draftComment.update((m) => { const n = { ...m }; delete n[id]; return n; });
      },
      error: () => {},
    });
  }

  private maybeAssess(paper: Paper): void {
    if (!paper.bib_id) return;
    const id = paper.bib_id;
    const phase_id = this.draftPhase()[id];
    const criterion_id = this.draftCriterion()[id];
    const researcher_email = this.session.currentResearcherEmail();

    if (!phase_id || !criterion_id || !researcher_email) return;

    const comment = this.draftComment()[id] || null;
    this.snower.assessPaper(id, { criterion_id, phase_id, researcher_email, comment }).subscribe({
      next: (updated) => {
        this.papers.update((list) => list.map((p) => (p.bib_id === id ? { ...p, decision: updated.decision } : p)));
        this.assessmentMaps.update((all) => ({ ...all, [id]: updated.assessments ?? {} }));
      },
      error: () => {},
    });
  }

  protected getDraftPhase(bibId: string): string {
    return this.draftPhase()[bibId] ?? '';
  }

  protected getDraftCriterion(bibId: string): string {
    return this.draftCriterion()[bibId] ?? '';
  }

  protected getDraftComment(bibId: string): string {
    return this.draftComment()[bibId] ?? '';
  }

  protected getAssessments(bibId: string): Array<{ email: string; name: string; assessment: Assessment }> {
    const map = this.assessmentMaps()[bibId] ?? {};
    const nameMap = Object.fromEntries(this.session.researchers().map((r) => [r.email, r.name]));
    return Object.entries(map)
      .map(([email, assessment]) => ({ email, name: nameMap[email] ?? email, assessment }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

}
