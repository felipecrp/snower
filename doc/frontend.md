# Frontend

The Snower frontend is an Angular 22 SPA (single-page application) located in `frontend/`.

## Tech stack

- **Angular 22** — standalone components, signals, lazy-loaded routes.
- **Bootstrap 5** (SCSS) — styling via semantic `@extend` classes; no raw Bootstrap classes appear in templates.
- **Bootstrap Icons** — icon font; glyphs wired through SCSS `@extend`.

## Structure

```
frontend/src/
  app/
    app.ts              Root shell component (sidebar state, researcher selector)
    app.html            Shell template: topbar · researcher select · sidebar nav · <router-outlet>
    app.routes.ts       Routes: project / import / snowballing (lazy loadComponent)
    app.config.ts       ApplicationConfig: provideRouter + provideHttpClient
    models/
      snower.models.ts  TypeScript interfaces mirroring the REST API payloads
    services/
      snower.service.ts HTTP gateway for all API calls (base URL: localhost:8000)
      session.service.ts UI session state: currentResearcherEmail signal (persisted to localStorage)
    pages/
      project/          ProjectPage — project name, seed list, per-set stat cards, CRUD tabs
      import-papers/    ImportPapersPage — BibTeX textarea, "as seed" toggle, results
      snowballing/      SnowballingPage — two-pane set list + assessment controls
  styles.scss           Global SCSS: Bootstrap import + all semantic @extend classes
```

## Styling convention

All Bootstrap-based styling lives in `src/styles.scss` as semantic classes that `@extend` Bootstrap selectors. Component stylesheets and templates never reference Bootstrap utility classes directly.

Example:

```scss
.btn-include {
  @extend .btn;
  @extend .btn-sm;
  @extend .btn-success;
}
```

Templates then use `.btn-include`, `.panel`, `.set-item`, etc.

## Running locally

```bash
# Backend (from repo root)
SNOWER_PROJECT_PATH=./projects/<name> uv run uvicorn snower.api.app:app --reload

# Frontend
cd frontend
npm start          # serves at http://localhost:4200
npm run build      # production build
```

CORS is configured in `snower/api/app.py` to allow `http://localhost:4200`.

## Services

### `SnowerService`

HTTP gateway; one method per API route. Mutating CRUD methods (`createCriterion`, `updatePhase`, `deleteResearcher`, etc.) type the response as `void` — the backend returns no body on 201/204. `assessPaper` returns an `AssessmentMap`. All id/email URL segments use `encodeURIComponent`.

### `SessionService`

Holds `currentResearcherEmail: Signal<string | null>`. Persists to `localStorage` under `snower.currentResearcherEmail` so the selection survives page reloads. Kept separate from `SnowerService` so the HTTP gateway has a single responsibility.

## Pages

### Setup / Project (`/setup`)

Loads `GET /` (`ProjectSummary`, which now includes `criteria`, `phases`, and `researchers`) and displays:

- **Tabbed CRUD panel** with three tabs:
  - **Criteria** — table with id, name, and type (inclusion/exclusion); inline edit + delete; add-row at the bottom. Shows 409 duplicate error.
  - **Phases** — table with id and name; inline edit + delete; add-row.
  - **Researchers** — table with email and name; inline edit + delete; add-row.
- Project name, seed list, and per-set stat cards (below the tabs).

### Search / Import (`/import`)

- BibTeX textarea bound to a signal.
- "Import as seed" checkbox.
- On submit, calls `POST /import`; shows imported IDs and skipped messages.

### Snowballing (`/snowballing`)

Two-pane layout:

- **Left** — list of all derived sets (`GET /sets`); clicking selects a set.
- **Right** — papers for the selected set (`GET /sets/{set_name}/papers`); each paper shows:
  - Phase and criterion `<select>` dropdowns. When both are chosen and a researcher is selected in the top bar, the assessment is auto-submitted via `PATCH /papers/{bib_id}`.
  - If no researcher is selected, the dropdowns are disabled with a hint.
  - Existing assessments are shown as a compact list: `email · included/excluded badge · criterion name · phase name`.
  - `Assessment.included` is derived client-side via `isIncluded(a) → a.criterion.type === 'inclusion'`; the backend does not serialize this field.

## Top-bar current researcher

The root shell (`app.ts` / `app.html`) loads the researcher list on init and renders a `<select class="researcher-select">` in the topbar. Selecting a researcher writes to `SessionService.currentResearcherEmail` (and `localStorage`). The Snowballing page reads this signal to gate and populate assessments.

## Models

Key additions over the original API contract:

| Type | Description |
|------|-------------|
| `Criterion` | `{ id, name, type: CriterionType }` |
| `Phase` | `{ id, name }` |
| `Researcher` | `{ email, name }` |
| `Assessment` | `{ criterion: Criterion, phase: Phase }` |
| `AssessmentMap` | `Record<string, Assessment>` — email → Assessment |
| `isIncluded(a)` | Helper: `a.criterion.type === 'inclusion'` |

`ProjectSummary` now includes `criteria`, `phases`, and `researchers` arrays.
