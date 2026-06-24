import { Component, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

/**
 * Root shell component.
 *
 * Owns the sidebar collapsed state and renders the topbar, sidebar nav, and
 * the routed page area.
 */
@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  protected readonly collapsed = signal(false);

  protected toggleSidebar(): void {
    this.collapsed.update((v) => !v);
  }
}
