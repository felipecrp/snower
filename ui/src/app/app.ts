import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit, computed, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ProjectService } from './project.service';
import { ResearcherService } from './researcher.service';

const TAB_ORDER = ['project', 'snowballing', 'results'];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  readonly projectSvc = inject(ProjectService);
  private readonly researcherSvc = inject(ResearcherService);
  private readonly router = inject(Router);

  readonly project = this.projectSvc.project;
  readonly activeResearcherId = this.researcherSvc.activeId;

  readonly selectValue = computed(() => this.activeResearcherId());

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
