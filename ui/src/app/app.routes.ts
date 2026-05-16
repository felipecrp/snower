import { Routes } from '@angular/router';

import { SettingsComponent } from './settings/settings';
import { TriageComponent } from './triage/triage';

export const routes: Routes = [
  { path: '', component: TriageComponent },
  { path: 'settings', component: SettingsComponent },
];
