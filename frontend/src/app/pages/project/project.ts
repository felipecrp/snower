import { Component, OnInit, inject, signal } from '@angular/core';

import { ProjectSummary } from '../../models/snower.models';
import { SnowerService } from '../../services/snower.service';

/**
 * Project page — shows the project name, seed papers, and per-set statistics.
 */
@Component({
  selector: 'app-project',
  templateUrl: './project.html',
})
export class ProjectPage implements OnInit {
  private readonly snower = inject(SnowerService);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly project = signal<ProjectSummary | null>(null);

  ngOnInit(): void {
    this.snower.getProjectSummary().subscribe({
      next: (data) => {
        this.project.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.message ?? 'Failed to load project');
        this.loading.set(false);
      },
    });
  }
}
