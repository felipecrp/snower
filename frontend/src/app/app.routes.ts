import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'setup', pathMatch: 'full' },
  {
    path: 'setup',
    loadComponent: () =>
      import('./pages/project/project').then((m) => m.ProjectPage),
  },
  {
    path: 'import',
    loadComponent: () =>
      import('./pages/import-papers/import-papers').then(
        (m) => m.ImportPapersPage,
      ),
  },
  {
    path: 'snowballing',
    loadComponent: () =>
      import('./pages/snowballing/snowballing').then((m) => m.SnowballingPage),
  },
  {
    path: 'analysis',
    loadComponent: () =>
      import('./pages/analysis/analysis').then((m) => m.AnalysisPage),
  },
  {
    path: 'report',
    loadComponent: () =>
      import('./pages/report/report').then((m) => m.ReportPage),
  },
  {
    path: 'export',
    loadComponent: () =>
      import('./pages/export/export').then((m) => m.ExportPage),
  },
];
