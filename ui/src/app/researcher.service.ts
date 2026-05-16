import { Injectable, signal } from '@angular/core';

const STORAGE_KEY = 'snow.activeResearcherId';

@Injectable({ providedIn: 'root' })
export class ResearcherService {
  readonly activeId = signal<string | null>(this.read());

  set(id: string | null): void {
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    this.activeId.set(id);
  }

  private read(): string | null {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }
}
