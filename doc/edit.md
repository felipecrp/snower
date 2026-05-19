# Editing BibTeX

Researchers can edit the raw BibTeX of any imported paper directly from the UI, without touching files on disk manually.

## Opening the editor

- Click the **pen icon** (✏) on any paper card in the Snowballing panel.
- Or select a paper and press **`v e`** (keyboard shortcut).

The modal shows the paper's current `.bib` file content in a monospace textarea.

## Saving

Edit the BibTeX text and click **Save**. The backend:

1. Parses the text with `bibtexparser`. Syntax errors are shown inline; save is blocked until fixed.
2. Forces the entry key to the original `bib_key` — you cannot rename the file via this dialog.
3. Writes `works/<bib_key>.bib` with the updated content.
4. Adds the new full fingerprint to `keys.yml` (pointing to the same `bib_key`) if identity fields changed. The old fingerprint is **not** removed, so historical imports still deduplicate correctly.
5. Returns the parsed `Work`, which the UI uses to refresh the card immediately.

## Identity preservation

The paper's `bib_key` (and therefore its file path, decisions, relations, and set membership) never changes across edits. Only the *fingerprint index* grows when title/authors/year are modified.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/works/{bib_key}/bibtex` | Returns `{ "bibtex": "<raw .bib text>" }` |
| `PUT` | `/api/works/{bib_key}/bibtex` | Body: `{ "bibtex": "..." }`. Returns the updated `Work` or `400` on parse/validation error. |

Error response shape (400):
```json
{ "detail": { "error": "parse", "message": "<bibtexparser message>" } }
```
