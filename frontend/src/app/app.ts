import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { SessionService } from './services/session.service';
import { SnowerService } from './services/snower.service';

/**
 * Root shell component.
 *
 * Loads the project summary on init to display the project name in the topbar
 * and in the browser tab title ("Snower – <name>"). Also loads the researcher
 * list for the current-researcher selector.
 */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly snower = inject(SnowerService);
  private readonly titleService = inject(Title);
  protected readonly session = inject(SessionService);

  protected readonly collapsed = signal(false);
  protected readonly projectName = signal<string | null>(null);
  protected readonly sortedResearchers = computed(() =>
    [...this.session.researchers()].sort((a, b) => a.name.localeCompare(b.name))
  );

  ngOnInit(): void {
    this.snower.getProjectSummary().subscribe({
      next: (data) => {
        this.projectName.set(data.name);
        this.session.researchers.set(data.researchers);
        this.titleService.setTitle(`Snower – ${data.name}`);
      },
      error: () => {},
    });
  }

  protected toggleSidebar(): void {
    this.collapsed.update((v) => !v);
  }

  protected onResearcherChange(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.session.setResearcher(value || null);
  }
}
