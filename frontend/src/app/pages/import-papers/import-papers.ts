import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ImportResult } from '../../models/snower.models';
import { SnowerService } from '../../services/snower.service';

/**
 * Import page — paste BibTeX to import papers, optionally as seeds.
 */
@Component({
  selector: 'app-import-papers',
  imports: [FormsModule],
  templateUrl: './import-papers.html',
})
export class ImportPapersPage {
  private readonly snower = inject(SnowerService);

  protected readonly bibtex = signal('');
  protected readonly asSeed = signal(false);
  protected readonly submitting = signal(false);
  protected readonly result = signal<ImportResult | null>(null);
  protected readonly error = signal<string | null>(null);

  protected setBibtex(value: string): void {
    this.bibtex.set(value);
  }

  protected setAsSeed(value: boolean): void {
    this.asSeed.set(value);
  }

  protected submit(): void {
    this.result.set(null);
    this.error.set(null);
    this.submitting.set(true);

    this.snower.importBibtex(this.bibtex(), this.asSeed()).subscribe({
      next: (data) => {
        this.result.set(data);
        this.bibtex.set('');
        this.submitting.set(false);
      },
      error: (err) => {
        this.error.set(err?.message ?? 'Import failed');
        this.submitting.set(false);
      },
    });
  }
}
