import { Component, Input, inject } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

const ICONS: Record<string, string> = {
  settings:
    '<circle cx="12" cy="12" r="3"/>' +
    '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',

  search:
    '<circle cx="11" cy="11" r="8"/>' +
    '<path d="m21 21-4.3-4.3"/>',

  'bar-chart':
    '<path d="M12 20V10M18 20V4M6 20v-4"/>',

  minimize:
    '<path d="M5 12h14"/>',

  maximize:
    '<rect x="3" y="3" width="18" height="18" rx="2"/>',

  restore:
    '<rect x="8" y="8" width="13" height="13" rx="2"/>' +
    '<path d="M3 16V5a2 2 0 0 1 2-2h11"/>',

  close:
    '<path d="M18 6 6 18M6 6l12 12"/>',

  sun:
    '<circle cx="12" cy="12" r="4"/>' +
    '<path d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>',

  moon:
    '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
};

@Component({
  selector: 'app-icon',
  standalone: true,
  template: `<svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    [innerHTML]="svg"
    aria-hidden="true"
  ></svg>`,
  styles: [`:host { display: inline-flex; align-items: center; } svg { width: 1em; height: 1em; }`],
})
export class IconComponent {
  private sanitizer = inject(DomSanitizer);

  svg: SafeHtml = '';

  @Input() set name(value: string) {
    this.svg = this.sanitizer.bypassSecurityTrustHtml(ICONS[value] ?? '');
  }
}
