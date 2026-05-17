import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';

import { ApiService } from '../api.service';
import { Work } from '../models';
import { ProjectService } from '../project.service';

interface PendingWork {
  work: Work;
  status: 'pending' | 'importing' | 'done' | 'error';
  error?: string;
}

@Component({
  selector: 'app-start-set',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './start-set.html',
  styleUrl: './start-set.scss',
})
export class StartSetComponent {
  private readonly api = inject(ApiService);
  readonly projectSvc = inject(ProjectService);

  readonly error = signal<string | null>(null);
  readonly importing = signal(false);
  readonly pendingWorks = signal<PendingWork[]>([]);

  readonly startSet = computed(() =>
    this.projectSvc.sets().find((s) => s.id === '00-start') ?? null,
  );

  readonly works = computed<Work[]>(() => this.startSet()?.works ?? []);

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.importing.set(true);
    this.error.set(null);
    this.pendingWorks.set([]);
    input.value = '';

    this.projectSvc.markSetsPending(['00-start']);
    this.api.parseBib('00-start', file).subscribe({
      next: (works) => {
        this.pendingWorks.set(works.map((w) => ({ work: w, status: 'pending' })));
        this.importNext(0);
      },
      error: (e) => {
        this.error.set(`Parse failed: ${e.error?.detail ?? e.message}`);
        this.importing.set(false);
        this.projectSvc.clearSetsPending(['00-start']);
      },
    });
  }

  private importNext(index: number): void {
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
        this.projectSvc.sets.update((all) =>
          all.map((s) => {
            if (s.id !== '00-start') return s;
            const exists = s.works.findIndex((w) => w.id === importedWork.id);
            const works =
              exists >= 0
                ? s.works.map((w, i) => (i === exists ? importedWork : w))
                : [...s.works, importedWork];
            return { ...s, works };
          }),
        );
        this.pendingWorks.update((all) =>
          all.map((item, i) => (i === index ? { ...item, status: 'done' } : item)),
        );
        this.importNext(index + 1);
      },
      error: (e) => {
        this.pendingWorks.update((all) =>
          all.map((item, i) =>
            i === index
              ? { ...item, status: 'error', error: e.error?.detail ?? e.message }
              : item,
          ),
        );
        this.importNext(index + 1);
      },
    });
  }

  triggerFileInput(): void {
    document.getElementById('bib-file-input')?.click();
  }

  trackById = (_: number, x: { id: string }) => x.id;
  trackByIndex = (i: number) => i;
}
