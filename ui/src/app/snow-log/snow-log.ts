import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from '../api.service';
import { ReviewSet, SetKind, Work } from '../models';
import { ProjectService } from '../project.service';

interface AcceptedWork {
  work: Work;
  set: ReviewSet;
  backwardDone: boolean;
  forwardDone: boolean;
}

interface RunProgress {
  kind: Exclude<SetKind, 'start'>;
  done: number;
  total: number;
  currentKey: string | null;
}

@Component({
  selector: 'app-snow-log',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './snow-log.html',
  styleUrl: './snow-log.scss',
})
export class SnowLogComponent {
  private readonly api = inject(ApiService);
  readonly projectSvc = inject(ProjectService);

  readonly selected = signal<Set<string>>(new Set());
  readonly running = signal(false);
  readonly progress = signal<RunProgress | null>(null);
  readonly error = signal<string | null>(null);

  readonly acceptedWorks = computed<AcceptedWork[]>(() => {
    const sets = this.projectSvc.sets();
    const allDecisions = this.projectSvc.allDecisions();
    const result: AcceptedWork[] = [];

    for (const s of sets) {
      const decisions = allDecisions[s.id] ?? [];
      const voteCounts: Record<string, { accept: number; reject: number }> = {};
      for (const d of decisions) {
        if (!voteCounts[d.work_id]) voteCounts[d.work_id] = { accept: 0, reject: 0 };
        if (d.verdict === 'accept') voteCounts[d.work_id].accept++;
        else voteCounts[d.work_id].reject++;
      }
      for (const work of s.works) {
        const votes = voteCounts[work.id];
        if (!votes || votes.accept <= votes.reject) continue;
        result.push({
          work,
          set: s,
          backwardDone: !!work.last_backward_snowballed_at,
          forwardDone: !!work.last_forward_snowballed_at,
        });
      }
    }
    return result;
  });

  readonly stats = computed(() => {
    const works = this.acceptedWorks();
    const total = works.length;
    const backwardDone = works.filter((w) => w.backwardDone).length;
    const forwardDone = works.filter((w) => w.forwardDone).length;
    return { total, backwardDone, forwardDone };
  });

  readonly backwardPct = computed(() => {
    const { total, backwardDone } = this.stats();
    return total ? Math.round((backwardDone / total) * 100) : 0;
  });

  readonly forwardPct = computed(() => {
    const { total, forwardDone } = this.stats();
    return total ? Math.round((forwardDone / total) * 100) : 0;
  });

  isSelected(bibKey: string): boolean {
    return this.selected().has(bibKey);
  }

  toggleSelect(bibKey: string): void {
    this.selected.update((s) => {
      const next = new Set(s);
      if (next.has(bibKey)) next.delete(bibKey);
      else next.add(bibKey);
      return next;
    });
  }

  selectUnsnowballed(kind: 'backward' | 'forward'): void {
    const keys = this.acceptedWorks()
      .filter((w) => (kind === 'backward' ? !w.backwardDone : !w.forwardDone))
      .map((w) => w.work.bib_key);
    this.selected.set(new Set(keys));
  }

  clearSelection(): void {
    this.selected.set(new Set());
  }

  selectedCount(): number {
    return this.selected().size;
  }

  async runSnowballing(kind: Exclude<SetKind, 'start'>): Promise<void> {
    const keys = [...this.selected()];
    if (!keys.length) return;

    this.running.set(true);
    this.error.set(null);
    this.progress.set({ kind, done: 0, total: keys.length, currentKey: null });

    for (const bibKey of keys) {
      this.progress.update((p) => p ? { ...p, currentKey: bibKey } : p);
      try {
        const updatedSets = await firstValueFrom(this.api.runPaperSnowballing(kind, bibKey));
        this.mergeSets(updatedSets);
        // Reload decisions for any new/updated sets
        for (const s of updatedSets) {
          this.projectSvc.loadDecisionsForSet(s.id);
        }
      } catch (e: any) {
        this.error.set(`Error snowballing ${bibKey}: ${e.error?.detail ?? e.message}`);
      }
      this.progress.update((p) => p ? { ...p, done: p.done + 1 } : p);
    }

    this.running.set(false);
    this.progress.set(null);
    // Full refresh to pick up snowball timestamps on moved/updated works
    this.projectSvc.refresh();
  }

  private mergeSets(updatedSets: ReviewSet[]): void {
    this.projectSvc.sets.update((all) => {
      const byId = new Map(all.map((s) => [s.id, s]));
      for (const s of updatedSets) byId.set(s.id, s);
      return [...byId.values()].sort((a, b) => a.id.localeCompare(b.id));
    });
  }

  trackByKey = (_: number, w: AcceptedWork) => w.work.bib_key;
}
