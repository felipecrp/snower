import { Component, OnInit, computed, inject, signal } from '@angular/core';

import { Paper, SetSummary, setKey } from '../../models/snower.models';
import { SnowerService } from '../../services/snower.service';

/**
 * Snowballing page — browse derived sets and screen individual papers.
 *
 * Left pane lists all sets; selecting one loads its papers on the right.
 * Each paper shows an include/exclude button that calls screenPaper() and
 * then refreshes both the set list and the paper list.
 */
@Component({
  selector: 'app-snowballing',
  templateUrl: './snowballing.html',
})
export class SnowballingPage implements OnInit {
  private readonly snower = inject(SnowerService);

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

  protected readonly screeningId = signal<string | null>(null);

  protected readonly setKey = setKey;

  protected setLabel(set: SetSummary): string {
    if (set.name === 'start_set') return 'Start Set';
    if (set.name === 'orphans') return 'Orphans';
    return `${set.name} · round ${set.round}`;
  }

  ngOnInit(): void {
    this.loadSets();
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
      next: (data) => {
        this.papers.set(data);
        this.loadingPapers.set(false);
      },
      error: (err) => {
        this.papersError.set(err?.message ?? 'Failed to load papers');
        this.loadingPapers.set(false);
      },
    });
  }

  protected screen(paper: Paper, included: boolean): void {
    if (!paper.bib_id) return;
    this.screeningId.set(paper.bib_id);

    this.snower.screenPaper(paper.bib_id, included).subscribe({
      next: () => {
        this.screeningId.set(null);
        this.papers.update(ps =>
          ps.map(p => p.bib_id === paper.bib_id ? { ...p, included } : p),
        );
        this.loadSets();
      },
      error: () => {
        this.screeningId.set(null);
      },
    });
  }

  protected isScreening(paper: Paper): boolean {
    return this.screeningId() === paper.bib_id;
  }
}
