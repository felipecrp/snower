# Paper Identity

Snow identifies each paper by a human-readable **bib_key** (e.g. `wohlin2014snowballing`).
The global registry `keys.yml` maps cryptographic fingerprints to bib_keys, enabling
deduplication across import sources without ever comparing mutable metadata.

---

## Fingerprints

Two hash functions are used, both computed from normalized metadata.

### Normalization rules

| Field | Rule |
|---|---|
| Author surname | Unicode NFKD → ASCII fold; take only the surname (before comma, or last word) |
| Title | Unicode NFKD → ASCII fold; strip punctuation; collapse whitespace; lowercase |
| Year | Decimal string, or `""` if absent |

DOI and venue are **not** used in fingerprints — they are metadata, not identity.

### Full fingerprint (`sha1full:`)

```
payload = surname₁|surname₂|…|year|full_normalized_title
sha1full:<40-char hex of SHA-1(payload)>
```

Used for **exact deduplication**: the same paper re-imported from the same source always
produces the same full fingerprint.

### Short fingerprint (`sha1short:`)

```
payload = surname₁|surname₂|year|word₁|word₂|word₃
sha1short:<8-char hex of SHA-1(payload)>
```

Only the **first two author surnames** and the **first three significant title words**
(≥ 5 characters, skipping stop-word-length tokens) are used. This tolerates sources that
omit trailing co-authors or truncate long titles.

---

## `bib_key` generation algorithm

On every paper import `_renormalize_keys()` runs the following steps:

1. **Full fingerprint match** → the paper is already known; reuse its bib_key. Done.
2. **Short fingerprint match** → assumed to be the same paper from a different source;
   register a new full-hash entry pointing to the same bib_key. Done.
3. **No match** → mint a new bib_key:
   - Base: `<surname><year><first-significant-title-word>` (first word ≥ 5 chars; fallback to
     the first word of any length; `untitled` if the title is absent; `anon` if no authors;
     `nd` if no year).
   - Collision: if the base key is already in use, append `2`, then `3`, etc. until free.
   - Register a new entry in `keys.yml`.

### Example

Paper: Wohlin, Claus (2014) — "Snowballing in systematic literature reviews"

```
surname  = "wohlin"
year     = "2014"
slug     = "snowballing"   ← first significant word (≥ 5 chars)
bib_key  = "wohlin2014snowballing"
```

---

## `keys.yml` format

```yaml
keys:
  sha1full:3f2e1a...:          # full fingerprint
    short: sha1short:7775895b  # short fingerprint
    bib_key: wohlin2014snowballing
  sha1full:deadbeef...:        # second full fingerprint → same paper, different source
    short: sha1short:7775895b  # same short hash
    bib_key: wohlin2014snowballing
  sha1full:cafebabe...:        # different paper
    short: sha1short:9a3bc1d2
    bib_key: wohlin2014snowballing2
```

Entries are sorted by full fingerprint for stable git diffs.

---

## Collision scenarios

| Scenario | Outcome |
|---|---|
| Same paper re-imported from the same source | Full hash match → same bib_key (no change) |
| Same paper from a different source (partial authors/title) | Short hash match → same bib_key; new full-hash entry added |
| Different papers with the same short hash (rare) | Treated as same paper; manual split required (see below) |
| Different papers with the same slug | Sequential suffix: `wohlin2014snowballing`, `wohlin2014snowballing2`, … |
| Cryptographic full-hash collision | Negligible probability |

---

## Manual merge (two entries for one paper)

If `keys.yml` has two separate bib_keys for the same paper (e.g. the short hash
match failed because a title was significantly different):

1. Decide which bib_key to keep (e.g. `wohlin2014snowballing`).
2. Edit `keys.yml`: change the `bib_key` field of the second entry to match the first.
3. Rename any decision files that reference the discarded key.
4. Re-run the server; the next import will honour the updated registry.

```yaml
# Before
sha1full:aaa...:
  short: sha1short:11111111
  bib_key: wohlin2014snowballing
sha1full:bbb...:
  short: sha1short:22222222
  bib_key: wohlin2014guidelines   # ← same paper, wrong key

# After
sha1full:aaa...:
  short: sha1short:11111111
  bib_key: wohlin2014snowballing
sha1full:bbb...:
  short: sha1short:22222222
  bib_key: wohlin2014snowballing  # ← corrected
```

---

## Manual split (one bib_key for two different papers)

This happens when two genuinely different papers share the same short fingerprint (rare).
The system merged them automatically; you need to give the second paper its own key.

1. Identify the two full fingerprints that map to the same bib_key.
2. Edit `keys.yml`: change the `bib_key` of the second entry to a new unique key
   (e.g. `wohlin2014snowballing2`).
3. Rename the decision file for the affected paper to use the new bib_key.
4. Create a corresponding work `.bib` file under `works/` if needed.

```yaml
# Before — incorrect merge
sha1full:aaa...:
  short: sha1short:11111111
  bib_key: wohlin2014snowballing
sha1full:ccc...:               # different paper, same short hash
  short: sha1short:11111111
  bib_key: wohlin2014snowballing  # ← wrong, must be split

# After
sha1full:aaa...:
  short: sha1short:11111111
  bib_key: wohlin2014snowballing
sha1full:ccc...:
  short: sha1short:11111111
  bib_key: wohlin2014snowballing2  # ← split into its own key
```

After editing, update any `decisions_*.yml` files that referenced the old key for that paper.
