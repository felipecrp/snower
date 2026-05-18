import { CommonModule } from '@angular/common';
import { Component, computed, inject } from '@angular/core';

import { ApiService } from '../api.service';
import { Decision, ReviewSet, Work } from '../models';
import { ProjectService } from '../project.service';

type ConsensusStatus = 'accept' | 'reject' | 'unresolved';

interface AcceptedPaper {
  work: Work;
  setId: string;
  setKind: ReviewSet['kind'];
  iteration: number;
}

interface SetSummary {
  set: ReviewSet;
  total: number;
  accepted: number;
  rejected: number;
  unresolved: number;
  acceptanceRate: number;
  acceptedPapers: AcceptedPaper[];
}

interface OverviewSummary {
  total: number;
  accepted: number;
  rejected: number;
  unresolved: number;
  acceptanceRate: number;
}

interface GroupSummary {
  label: string;
  count: number;
  papers: AcceptedPaper[];
}

interface IterationSummary {
  iteration: number;
  total: number;
  accepted: number;
  rejected: number;
  unresolved: number;
  sections: SetSummary[];
}

function sortSets(left: ReviewSet, right: ReviewSet): number {
  if (left.iteration !== right.iteration) return left.iteration - right.iteration;
  return left.id.localeCompare(right.id);
}

function classifyConsensus(decisions: Decision[], bibKey: string): ConsensusStatus {
  let accept = 0;
  let reject = 0;
  for (const decision of decisions) {
    if (decision.bib_id !== bibKey) continue;
    if (decision.verdict === 'accept') accept += 1;
    else reject += 1;
  }
  if (accept > reject) return 'accept';
  if (reject > accept) return 'reject';
  return 'unresolved';
}

export function buildSetSummaries(
  sets: ReviewSet[],
  allDecisions: Record<string, Decision[]>,
): SetSummary[] {
  return [...sets]
    .filter((set) => set.kind !== 'orphan')
    .sort(sortSets)
    .map((set) => {
      const decisions = allDecisions[set.id] ?? [];
      const acceptedPapers: AcceptedPaper[] = [];
      let accepted = 0;
      let rejected = 0;
      let unresolved = 0;

      for (const work of set.works) {
        const status = classifyConsensus(decisions, work.bib_key);
        if (status === 'accept') {
          accepted += 1;
          acceptedPapers.push({
            work,
            setId: set.id,
            setKind: set.kind,
            iteration: set.iteration,
          });
        } else if (status === 'reject') {
          rejected += 1;
        } else {
          unresolved += 1;
        }
      }

      const total = set.works.length;
      return {
        set,
        total,
        accepted,
        rejected,
        unresolved,
        acceptanceRate: total ? Math.round((accepted / total) * 100) : 0,
        acceptedPapers,
      };
    });
}

export function buildOverviewSummary(setSummaries: SetSummary[]): OverviewSummary {
  let total = 0;
  let accepted = 0;
  let rejected = 0;
  let unresolved = 0;

  for (const summary of setSummaries) {
    total += summary.total;
    accepted += summary.accepted;
    rejected += summary.rejected;
    unresolved += summary.unresolved;
  }

  return {
    total,
    accepted,
    rejected,
    unresolved,
    acceptanceRate: total ? Math.round((accepted / total) * 100) : 0,
  };
}

export function buildGroups(
  acceptedPapers: AcceptedPaper[],
  keyFor: (paper: AcceptedPaper) => string,
): GroupSummary[] {
  const grouped = new Map<string, AcceptedPaper[]>();
  for (const paper of acceptedPapers) {
    const key = keyFor(paper);
    const current = grouped.get(key);
    if (current) current.push(paper);
    else grouped.set(key, [paper]);
  }

  return [...grouped.entries()]
    .map(([label, papers]) => ({
      label,
      count: papers.length,
      papers: [...papers].sort((left, right) => {
        const yearDelta = (right.work.year ?? -1) - (left.work.year ?? -1);
        if (yearDelta !== 0) return yearDelta;
        return left.work.title.localeCompare(right.work.title);
      }),
    }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

export function buildIterationSummaries(setSummaries: SetSummary[]): IterationSummary[] {
  const grouped = new Map<number, SetSummary[]>();
  for (const summary of setSummaries) {
    const current = grouped.get(summary.set.iteration);
    if (current) current.push(summary);
    else grouped.set(summary.set.iteration, [summary]);
  }

  return [...grouped.entries()]
    .map(([iteration, sections]) => {
      const orderedSections = [...sections].sort((left, right) => left.set.id.localeCompare(right.set.id));
      let total = 0;
      let accepted = 0;
      let rejected = 0;
      let unresolved = 0;

      for (const section of orderedSections) {
        total += section.total;
        accepted += section.accepted;
        rejected += section.rejected;
        unresolved += section.unresolved;
      }

      return {
        iteration,
        total,
        accepted,
        rejected,
        unresolved,
        sections: orderedSections,
      };
    })
    .sort((left, right) => left.iteration - right.iteration);
}

@Component({
  selector: 'app-results',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './results.html',
  styleUrl: './results.scss',
})
export class ResultsComponent {
  private readonly api = inject(ApiService);
  readonly projectSvc = inject(ProjectService);

  readonly setSummaries = computed(() =>
    buildSetSummaries(this.projectSvc.sets(), this.projectSvc.allDecisions()),
  );

  readonly overview = computed(() => buildOverviewSummary(this.setSummaries()));

  readonly acceptedPapers = computed(() =>
    this.setSummaries().flatMap((summary) => summary.acceptedPapers),
  );

  readonly iterationSummaries = computed(() => buildIterationSummaries(this.setSummaries()));

  readonly venueGroups = computed(() =>
    buildGroups(
      this.acceptedPapers(),
      (paper) => paper.work.venue?.trim() || 'Unknown venue',
    ),
  );

  readonly yearGroups = computed(() =>
    buildGroups(
      this.acceptedPapers(),
      (paper) => paper.work.year?.toString() || 'Unknown year',
    ),
  );

  readonly orphanSummary = computed(() => {
    const orphanSet = this.projectSvc.sets().find((set) => set.kind === 'orphan');
    if (!orphanSet) return null;
    const decisions = this.projectSvc.allDecisions()[orphanSet.id] ?? [];
    let accepted = 0;
    let rejected = 0;
    let unresolved = 0;
    for (const work of orphanSet.works) {
      const status = classifyConsensus(decisions, work.bib_key);
      if (status === 'accept') accepted += 1;
      else if (status === 'reject') rejected += 1;
      else unresolved += 1;
    }
    return {
      total: orphanSet.works.length,
      accepted,
      rejected,
      unresolved,
    };
  });

  trackBySet = (_: number, summary: SetSummary) => summary.set.id;
  trackByIteration = (_: number, summary: IterationSummary) => summary.iteration;
  trackByGroup = (_: number, group: GroupSummary) => group.label;
  trackByPaper = (_: number, paper: AcceptedPaper) => `${paper.setId}:${paper.work.bib_key}`;

  hasPaperLinks(work: Work): boolean {
    return !!(work.url || work.doi || work.pdf_url || work.has_local_pdf);
  }

  localPdfUrl(bibKey: string): string {
    return this.api.localPdfUrl(bibKey);
  }
}
