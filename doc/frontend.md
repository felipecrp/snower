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
    app.ts              Root shell component (sidebar collapsed signal, topbar)
    app.html            Shell template: topbar · sidebar nav · <router-outlet>
    app.routes.ts       Routes: project / import / snowballing (lazy loadComponent)
    app.config.ts       ApplicationConfig: provideRouter + provideHttpClient
    models/
      snower.models.ts  TypeScript interfaces mirroring the REST API payloads
    services/
      snower.service.ts HTTP gateway for all API calls (base URL: localhost:8000)
    pages/
      project/          ProjectPage — project name, seed list, per-set stat cards
      import-papers/    ImportPapersPage — BibTeX textarea, "as seed" toggle, results
      snowballing/      SnowballingPage — two-pane set list + paper screener
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

## Pages

### Project (`/project`)

Loads `GET /` and displays:
- Project name and seed count.
- One stat card per derived set showing paper count, set name, and round number.

### Search / Import (`/import`)

- BibTeX textarea bound to a signal.
- "Import as seed" checkbox.
- On submit, calls `POST /import`; shows imported IDs and skipped messages.

### Snowballing (`/snowballing`)

Two-pane layout:

- **Left** — list of all derived sets (`GET /sets`); clicking selects a set.
- **Right** — papers for the selected set (`GET /sets/{set_name}/papers`); each paper shows an include/exclude button that calls `PATCH /papers/{bib_id}` and then refreshes both panes.
