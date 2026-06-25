import { Component, OnInit, computed, inject, signal } from '@angular/core';

import { Criterion, CriterionType, DecisionStrategy, Phase, ProjectSummary, Researcher } from '../../models/snower.models';
import { SessionService } from '../../services/session.service';
import { SnowerService } from '../../services/snower.service';

type ActiveTab = 'project' | 'criteria' | 'phases' | 'researchers';

/**
 * Project / Setup page — shows project name, seed papers, per-set statistics,
 * and CRUD tabs for criteria, phases, and researchers.
 */
@Component({
  selector: 'app-project',
  templateUrl: './project.html',
  host: { class: 'setup-page-host' },
})
export class ProjectPage implements OnInit {
  private readonly snower = inject(SnowerService);
  protected readonly session = inject(SessionService);

  protected readonly loading = signal(true);
  protected readonly error = signal<string | null>(null);
  protected readonly project = signal<ProjectSummary | null>(null);

  // ----- Tab state -------------------------------------------------------------

  protected readonly activeTab = signal<ActiveTab>('project');

  protected readonly criteria = signal<Criterion[]>([]);
  protected readonly phases = signal<Phase[]>([]);

  protected readonly sortedCriteria = computed(() =>
    [...this.criteria()].sort((a, b) => a.id.localeCompare(b.id))
  );
  protected readonly sortedPhases = computed(() =>
    [...this.phases()].sort((a, b) => a.id.localeCompare(b.id))
  );
  protected readonly sortedResearchers = computed(() =>
    [...this.session.researchers()].sort((a, b) => a.email.localeCompare(b.email))
  );

  // ----- New item form fields --------------------------------------------------

  protected readonly newInclusionId = signal('');
  protected readonly newInclusionName = signal('');
  protected readonly newExclusionId = signal('');
  protected readonly newExclusionName = signal('');
  protected readonly criterionError = signal<string | null>(null);

  protected readonly newPhaseId = signal('');
  protected readonly newPhaseName = signal('');
  protected readonly phaseError = signal<string | null>(null);

  protected readonly newResearcherEmail = signal('');
  protected readonly newResearcherName = signal('');
  protected readonly researcherError = signal<string | null>(null);

  // ----- Inline edit state -----------------------------------------------------

  protected readonly editingCriterion = signal<string | null>(null);
  protected readonly editCriterionId = signal('');
  protected readonly editCriterionName = signal('');
  protected readonly editCriterionType = signal<CriterionType>('inclusion');

  protected readonly editingPhase = signal<string | null>(null);
  protected readonly editPhaseId = signal('');
  protected readonly editPhaseName = signal('');

  protected readonly editingResearcher = signal<string | null>(null);
  protected readonly editResearcherEmail = signal('');
  protected readonly editResearcherName = signal('');

  protected readonly strategyError = signal<string | null>(null);

  ngOnInit(): void {
    this.snower.getProjectSummary().subscribe({
      next: (data) => {
        this.project.set(data);
        this.criteria.set(data.criteria);
        this.phases.set(data.phases);
        this.session.researchers.set(data.researchers);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.message ?? 'Failed to load project');
        this.loading.set(false);
      },
    });
  }

  protected setTab(tab: ActiveTab): void {
    this.activeTab.set(tab);
  }

  // ----- Criteria CRUD ---------------------------------------------------------

  protected addInclusionCriterion(): void {
    this.addCriterion(this.newInclusionId(), this.newInclusionName(), 'inclusion', () => {
      this.newInclusionId.set('');
      this.newInclusionName.set('');
    });
  }

  protected addExclusionCriterion(): void {
    this.addCriterion(this.newExclusionId(), this.newExclusionName(), 'exclusion', () => {
      this.newExclusionId.set('');
      this.newExclusionName.set('');
    });
  }

  private addCriterion(id: string, name: string, type: CriterionType, onSuccess: () => void): void {
    id = id.trim();
    name = name.trim();
    if (!id || !name) return;

    this.criterionError.set(null);
    this.snower.createCriterion({ id, name, type }).subscribe({
      next: () => { onSuccess(); this.refreshCriteria(); },
      error: (err) => {
        this.criterionError.set(err?.status === 409 ? 'Duplicate criterion id.' : 'Failed to create criterion.');
      },
    });
  }

  protected startEditCriterion(c: Criterion): void {
    this.editingCriterion.set(c.id);
    this.editCriterionId.set(c.id);
    this.editCriterionName.set(c.name);
    this.editCriterionType.set(c.type);
  }

  protected saveEditCriterion(originalId: string): void {
    const id = this.editCriterionId().trim();
    const name = this.editCriterionName().trim();
    const type = this.editCriterionType();
    this.criterionError.set(null);
    this.snower.updateCriterion(originalId, { id, name, type }).subscribe({
      next: () => { this.editingCriterion.set(null); this.refreshCriteria(); },
      error: (err) => this.criterionError.set(
        err?.status === 409 ? 'Duplicate criterion id.' : 'Failed to update criterion.'
      ),
    });
  }

  protected deleteCriterion(id: string): void {
    this.snower.deleteCriterion(id).subscribe({
      next: () => this.refreshCriteria(),
      error: () => this.criterionError.set('Failed to delete criterion.'),
    });
  }

  private refreshCriteria(): void {
    this.snower.getCriteria().subscribe({ next: (d) => this.criteria.set(d), error: () => {} });
  }

  // ----- Phases CRUD -----------------------------------------------------------

  protected addPhase(): void {
    const id = this.newPhaseId().trim();
    const name = this.newPhaseName().trim();
    if (!id || !name) return;

    this.phaseError.set(null);
    this.snower.createPhase({ id, name }).subscribe({
      next: () => {
        this.newPhaseId.set('');
        this.newPhaseName.set('');
        this.refreshPhases();
      },
      error: (err) => {
        this.phaseError.set(err?.status === 409 ? 'Duplicate phase id.' : 'Failed to create phase.');
      },
    });
  }

  protected startEditPhase(p: Phase): void {
    this.editingPhase.set(p.id);
    this.editPhaseId.set(p.id);
    this.editPhaseName.set(p.name);
  }

  protected saveEditPhase(originalId: string): void {
    const id = this.editPhaseId().trim();
    const name = this.editPhaseName().trim();
    this.phaseError.set(null);
    this.snower.updatePhase(originalId, { id, name }).subscribe({
      next: () => { this.editingPhase.set(null); this.refreshPhases(); },
      error: (err) => this.phaseError.set(
        err?.status === 409 ? 'Duplicate phase id.' : 'Failed to update phase.'
      ),
    });
  }

  protected deletePhase(id: string): void {
    this.snower.deletePhase(id).subscribe({
      next: () => this.refreshPhases(),
      error: () => this.phaseError.set('Failed to delete phase.'),
    });
  }

  private refreshPhases(): void {
    this.snower.getPhases().subscribe({ next: (d) => this.phases.set(d), error: () => {} });
  }

  // ----- Researchers CRUD ------------------------------------------------------

  protected addResearcher(): void {
    const email = this.newResearcherEmail().trim();
    const name = this.newResearcherName().trim();
    if (!email || !name) return;

    this.researcherError.set(null);
    this.snower.createResearcher({ email, name }).subscribe({
      next: () => {
        this.newResearcherEmail.set('');
        this.newResearcherName.set('');
        this.refreshResearchers();
      },
      error: (err) => {
        this.researcherError.set(err?.status === 409 ? 'Duplicate researcher email.' : 'Failed to create researcher.');
      },
    });
  }

  protected startEditResearcher(r: Researcher): void {
    this.editingResearcher.set(r.email);
    this.editResearcherEmail.set(r.email);
    this.editResearcherName.set(r.name);
  }

  protected saveEditResearcher(originalEmail: string): void {
    const email = this.editResearcherEmail().trim();
    const name = this.editResearcherName().trim();
    this.researcherError.set(null);
    this.snower.updateResearcher(originalEmail, { email, name }).subscribe({
      next: () => { this.editingResearcher.set(null); this.refreshResearchers(); },
      error: (err) => this.researcherError.set(
        err?.status === 409 ? 'Duplicate researcher email.' : 'Failed to update researcher.'
      ),
    });
  }

  protected deleteResearcher(email: string): void {
    this.snower.deleteResearcher(email).subscribe({
      next: () => this.refreshResearchers(),
      error: () => this.researcherError.set('Failed to delete researcher.'),
    });
  }

  private refreshResearchers(): void {
    this.session.refreshResearchers();
  }

  protected onStrategyChange(event: Event): void {
    const strategy = (event.target as HTMLSelectElement).value as DecisionStrategy;
    this.strategyError.set(null);
    this.snower.updateDecisionStrategy(strategy).subscribe({
      next: (data) => this.project.set(data),
      error: () => this.strategyError.set('Failed to update decision strategy.'),
    });
  }
}
