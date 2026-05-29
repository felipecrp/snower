import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit, computed, effect, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ProjectService } from './project.service';
import { ResearcherService } from './researcher.service';
import { IconComponent } from './shell/icon/icon';
import { TitleBarComponent } from './shell/title-bar/title-bar';

const TAB_ORDER = ['project', 'snowballing', 'results'];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterOutlet, RouterLink, RouterLinkActive, TitleBarComponent, IconComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  readonly projectSvc = inject(ProjectService);
  private readonly researcherSvc = inject(ResearcherService);
  private readonly router = inject(Router);

  readonly isElectron = !!(window as Window).snowShell?.isElectron;

  readonly project = this.projectSvc.project;
  readonly activeResearcherId = this.researcherSvc.activeId;

  readonly selectValue = computed(() => this.activeResearcherId());

  constructor() {
    effect(() => {
      if (this.projectSvc.workspaceLoaded() && !this.projectSvc.workspace()) {
        const current = this.router.url.split('?')[0].replace(/^\//, '');
        if (current !== 'project') {
          this.router.navigate(['/project']);
        }
      }
    });
  }

  ngOnInit(): void {
    this.projectSvc.bootstrapWorkspace();
  }

  onResearcherChange(value: string | null): void {
    this.researcherSvc.set(value || null);
  }

  @HostListener('document:keydown', ['$event'])
  handleKeyboard(event: KeyboardEvent): void {
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (this.isTypingTarget(event.target)) return;
    if (!event.shiftKey) return;
    if (event.key === 'L') {
      event.preventDefault();
      this.moveTab(1);
    } else if (event.key === 'H') {
      event.preventDefault();
      this.moveTab(-1);
    }
  }

  private moveTab(delta: number): void {
    const url = this.router.url.split('?')[0].replace(/^\//, '');
    const current = TAB_ORDER.indexOf(url);
    if (current === -1) return;
    const next = TAB_ORDER[Math.min(Math.max(current + delta, 0), TAB_ORDER.length - 1)];
    this.router.navigate([next]);
  }

  private isTypingTarget(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false;
    const tag = target.tagName.toLowerCase();
    return target.isContentEditable || tag === 'input' || tag === 'textarea' || tag === 'select';
  }
}
