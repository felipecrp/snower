import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';

import { ApiService } from '../api.service';
import { Work } from '../models';
import { ProjectService } from '../project.service';

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
    this.api.importBib('00-start', file).subscribe({
      next: (updatedSet) => {
        this.projectSvc.sets.update((all) =>
          all.map((s) => (s.id === '00-start' ? updatedSet : s)),
        );
        this.importing.set(false);
        input.value = '';
      },
      error: (e) => {
        this.error.set(`Import failed: ${e.error?.detail ?? e.message}`);
        this.importing.set(false);
        input.value = '';
      },
    });
  }

  triggerFileInput(): void {
    document.getElementById('bib-file-input')?.click();
  }

  trackById = (_: number, x: { id: string }) => x.id;
}
