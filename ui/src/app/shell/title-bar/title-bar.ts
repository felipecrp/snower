import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';

import { ProjectService } from '../../project.service';
import { ThemeService } from '../../theme.service';
import { IconComponent } from '../icon/icon';

@Component({
  selector: 'app-title-bar',
  standalone: true,
  imports: [CommonModule, IconComponent],
  templateUrl: './title-bar.html',
  styleUrl: './title-bar.scss',
})
export class TitleBarComponent implements OnInit {
  readonly projectSvc = inject(ProjectService);
  readonly themeSvc = inject(ThemeService);

  readonly isMaximized = signal(false);
  readonly platform = window.snowShell?.platform ?? 'linux';
  readonly showControls = this.platform !== 'darwin';

  ngOnInit(): void {
    window.snowShell?.onMaximizeChange((v) => this.isMaximized.set(v));
  }

  minimize(): void { window.snowShell?.minimize(); }
  maximizeToggle(): void { window.snowShell?.maximizeToggle(); }
  close(): void { window.snowShell?.close(); }
  toggleTheme(): void { this.themeSvc.toggle(); }
}
