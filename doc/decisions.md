# Design Decisions

This document records the key decisions made during development, including the reasoning behind each choice.

---

## No central works registry

**Decision:** `work_id` is computed on-the-fly when loading a `.bib` file. There is no `works.yml` or global paper index stored on disk.

**Why:** A central registry requires coordination every time a paper appears in a new set. Since `work_id` is deterministic (DOI > SHA-1 of surname+year+title), deduplication can be done in-memory by building a set of known ids when loading all sets. This keeps the on-disk format simpler and fully git-diffable.

**Trade-off:** Loading all sets to deduplicate is O(N × M) in papers. For the typical scale of a systematic review (hundreds to low thousands of papers), this is not a concern.

---

## BibTeX key format: `<surname><year><letter>`

**Decision:** Keys follow the pattern `wohlin2014a`, with letter suffix (`a..z`, then `aa..zz`) to avoid collisions. The mapping is persisted in `keys.yml`.

**Why:** Human-readable keys make the `.bib` files usable directly in LaTeX and readable in git diffs. The registry in `keys.yml` ensures the same paper always gets the same key across sets and sessions.

---

## Criterion drives verdict (no Accept/Reject buttons)

**Decision:** The triage UI has a single criterion dropdown. Selecting an `include` criterion produces an `accept` verdict; selecting an `exclude` criterion produces a `reject` verdict. There are no separate accept/reject buttons.

**Why:** In a rigorous systematic review, every decision must be justified by a criterion. Allowing a verdict without a criterion would produce untracked decisions that are hard to audit or reproduce. The keyboard shortcuts `a` (accept) and `r` (reject) open a fuzzy-search dialog that forces criterion selection before the decision is saved.

---

## All domain logic in Python

**Decision:** The Angular frontend is a pure UI layer. It calls the local API and renders the response. No business logic (deduplication, consensus, snowballing coordination, rename propagation) lives in TypeScript.

**Why:** Python is easier to test with a proper test suite (pytest) and the logic is reusable from the CLI. Keeping Angular as a thin client means the backend can be used independently (e.g. scripted imports, automated snowballing runs).

---

## Git as the multi-researcher collaboration model

**Decision:** There is no server-side authentication or session management. The active researcher is chosen from a dropdown in the UI and stored in `localStorage`. Multi-researcher collaboration happens via git branches and merges.

**Why:** The target users are research teams who already use git for paper management. A lightweight social trust model ("your name is in the branch you pushed") is sufficient and avoids the operational cost of running a real backend with user accounts.

---

## Researcher removal deletes their decisions

**Decision:** When a researcher is removed via `PUT /api/project/researchers`, all their decisions are deleted from every set's `decisions.yml`.

**Why:** A removed researcher's votes would silently affect consensus results. Keeping orphaned decisions would be confusing and misleading. Deletion is explicit and visible in the git diff.

---

## Snowballing is global, not per-set

**Decision:** The sidebar has a single Backward and Forward button that triggers snowballing for all accepted papers across all sets, not just the current one.

**Why:** The snowballing method naturally flows by iteration. Papers from iteration N (regardless of which set they are in — backward or forward) all feed into iteration N+1. Running snowballing per-set would create duplicate or misaligned sets. A global trigger that groups papers by iteration is the correct abstraction.

---

## Majority consensus for results view

**Decision:** A paper is considered accepted in the Results view if `accept_count > reject_count` among all researchers' decisions. Ties (including zero decisions) are not shown.

**Why:** Simple majority is the most common conflict resolution in systematic reviews with small teams. The implementation is purely frontend (no extra API call). A formal resolution mechanism (`Resolution` model) exists for when teams want to override the majority, but the UI does not yet expose it.

---

## Iteration numbering

**Decision:** Every set has an explicit `iteration: int` field (0 for start, 1 for first backward/forward round, etc.). The set directory name (`NN-kind`) encodes the same number for human readability.

**Why:** The iteration number is the key to understanding which papers feed into which snowballing round. Without it, the UI would have to infer the round from the parent chain, which is error-prone and requires loading the full graph.

---

## LaTeX decoding at parse time

**Decision:** BibTeX files from Scopus and other exporters contain LaTeX escape sequences (e.g. `{\'{e}}` for `é`). These are decoded to Unicode when loading via `bibtexparser.customization.convert_to_unicode`. The raw `.bib` files on disk remain unchanged.

**Why:** Storing the decoded form in the domain model allows the UI to display clean text without any client-side LaTeX rendering. The original `.bib` files are preserved as-is, which is important for interoperability with other tools.

---

## Google Scholar via `scholarly` (scraping)

**Decision:** The default snowballing provider uses the `scholarly` Python library, which scrapes Google Scholar.

**Why:** Google Scholar has no official API. `scholarly` is the de facto standard for programmatic access. It covers a wide range of papers including grey literature.

**Known limitations:**
- Google Scholar may return CAPTCHA responses after many requests. For large reviews, configure a proxy via `scholarly.use_proxy()`.
- References are not always available through Scholar (depends on the paper).
- Forward citations (citedby) can be slow to iterate for highly cited papers.

Alternative providers (Semantic Scholar, OpenAlex) may be added in the future via the `Provider` ABC in `snow/providers/base.py`.

---

## Electron in dev mode only

**Decision:** The Electron main process loads `http://localhost:4200` (the Angular dev server). There is no packaged Electron build yet.

**Why:** Packaging Electron for distribution (code signing, auto-update, platform installers) is significant overhead. The dev-mode Electron window gives a native desktop experience immediately, deferring the distribution problem to a future milestone.
