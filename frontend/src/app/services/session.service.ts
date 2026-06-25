import { Injectable, inject, signal } from '@angular/core';

import { Researcher } from '../models/snower.models';
import { SnowerService } from './snower.service';

const STORAGE_KEY = 'snower.currentResearcherEmail';

/**
 * Holds UI-session state that is shared across pages but not tied to
 * any HTTP resource. Kept separate from SnowerService so that the HTTP
 * gateway has a single responsibility.
 */
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly snower = inject(SnowerService);

  /** Email of the researcher currently performing assessments, or null if none selected. */
  readonly currentResearcherEmail = signal<string | null>(
    localStorage.getItem(STORAGE_KEY),
  );

  /** Shared researcher list — updated whenever the Researchers tab mutates data. */
  readonly researchers = signal<Researcher[]>([]);

  /** Persist the selected researcher across page reloads. */
  setResearcher(email: string | null): void {
    this.currentResearcherEmail.set(email);
    if (email) {
      localStorage.setItem(STORAGE_KEY, email);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  /** Reload the researcher list from the API and update the shared signal. */
  refreshResearchers(): void {
    this.snower.getResearchers().subscribe({ next: (d) => this.researchers.set(d), error: () => {} });
  }
}
