import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'analysis', pathMatch: 'full' },
  {
    path: 'settings',
    loadComponent: () => import('./settings/settings').then((m) => m.SettingsComponent),
  },
  {
    path: 'start-set',
    loadComponent: () => import('./start-set/start-set').then((m) => m.StartSetComponent),
  },
  {
    path: 'analysis',
    loadComponent: () => import('./analysis/analysis').then((m) => m.AnalysisComponent),
  },
  {
    path: 'snowballing',
    loadComponent: () => import('./snowballing/snowballing').then((m) => m.SnowballingComponent),
  },
];
