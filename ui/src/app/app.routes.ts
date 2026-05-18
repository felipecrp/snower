import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', redirectTo: 'snowballing', pathMatch: 'full' },
  {
    path: 'project',
    loadComponent: () => import('./project/project').then((m) => m.ProjectComponent),
  },
  {
    path: 'start-set',
    loadComponent: () => import('./start-set/start-set').then((m) => m.StartSetComponent),
  },
  {
    path: 'snowballing',
    loadComponent: () => import('./snowballing/snowballing').then((m) => m.SnowballingComponent),
  },
  {
    path: 'results',
    loadComponent: () => import('./results/results').then((m) => m.ResultsComponent),
  },
  {
    path: 'snow-log',
    loadComponent: () => import('./snow-log/snow-log').then((m) => m.SnowLogComponent),
  },
];
