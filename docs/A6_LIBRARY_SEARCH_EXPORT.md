# A6 — combined library and pre-search export

Status: complete on 2026-09-26 on `codex/applicability-library-a6`.

## Delivered

- `sme.library.verified_package` checks the neutral manifest/content contract,
  original-file inventory, every original hash, and any associated A4 evidence
  generation. `make_library` builds `service-manual-library/v1` with a distinct
  occurrence ID and relative root for every input package. Same-role books,
  duplicate packages and their original citations remain separate; the
  append-only review overlay carries any reviewed edition/equivalence link.
- `resolve_scope` applies the A5 matcher to active cited units **before** text
  retrieval. It emits `vehicle-scope/v1`, reasons, source/review IDs, counts and
  a no-content state. Empty non-browse scope has no eligible text. Unknown or
  unmapped input never silently widens the scope. A bounded LRU cache keys on
  library, vocabulary and review revisions plus the exact selection/mode.
- `publish_library` copies validated packages into an immutable generation,
  exports known full and partial vehicle scopes (including missing qualifier
  selections), then groups text into membership-homogeneous bounded shards.
  It records explicit unsupported-input states supplied by discovery. Shards
  contain only units eligible together, and each shard is content-hash checked
  at query time. Generation identity includes source/library and transformation
  revisions. A generation is activated only after complete publication.
- `search_export` resolves the selected scope fingerprint, rejects a stale
  review revision, loads only that scope's shards, and then tokenizes, ranks,
  forms snippets and applies the result limit. A cancellation callback can
  interrupt an obsolete request. A selected scope not present in the static
  export fails clearly; it does not fall back to global search. Python
  `resolve_scope` remains available for on-demand selections.
- `open_current` requires the **current** trusted review revision. If a new
  review revokes approval and a rebuild fails, old content remains on disk and
  readable, but its old search index is rejected under the new revision.

## Verification

- Combined authored library: two Ford workshop books, a static HTML manual,
  a GM PDF and a duplicate Ford package. Four package occurrences and both
  Ford books remain distinct. A Ford 6.0L search loaded no GM-only shard;
  querying the GM-only phrase under the Ford scope returned no result without
  reading GM text. A duplicate source unit retained two occurrence links.
- Every static scope in a qualifier-bearing Ford fixture equaled the Python
  scope result, including make/model/year partial filters, full vehicle with
  missing transmission, and full vehicle with known transmission. Confirmed
  search excluded the transmission-restricted book until the qualifier was
  supplied; possible mode showed it with its reason.
- A simulated generation-build failure left the prior generation intact.
  `open_current` and `search_export` rejected the old index when supplied the
  new revoked review revision. Atomic publish then created a new generation.
  Cancellation, bounded cache eviction, explicit unsupported input and empty
  non-browse scope were tested.
- Full extractor suite: 177 tests passed, with one opt-in real-OCR test skipped.
  Ruff and `git diff --check` passed. The earlier A4 real-OCR gate remains
  recorded separately.

## Scope and limits

- This export is a portable Python/offline data boundary. Repair Buddy and the
  browser viewer do not consume it yet; those are A7 and A9. The caller must
  obtain the current review revision from its trusted review store for every
  search, not from an old export. Old immutable content can remain readable
  while its eligibility is invalid.
- Static scopes include all qualifier-presence subsets for configurations with
  up to six known qualifier keys. For more keys, the export keeps the empty,
  full, singleton and one-missing states; other combinations require on-demand
  Python evaluation or a tailored rebuild. Unsupported selections never fall
  back to an unrestricted shard. One unusually long unit can exceed the shard
  character target because it cannot be split without a reliable subunit.
- No real 113-PDF plus Ford library was copied into a new generation in A6;
  the acceptance suite uses small authored fixtures. The replacement GM HTML
  path is still pending, so its real-source coverage remains unclaimed.

## Next step

A7 migrates Repair Buddy on a separate clean branch/worktree and pins this
extractor revision. It must back up and migrate a **disposable copy** of the
existing database first, import the shared library (including the 280-page
legacy owner guide), and make all search routes use the same pre-search unit
allowlist. Existing Ford IDs, citations, source pages, review history and user
documentation edits must survive. Pass when Ford-only search never visits GM
text across primary, conflict, legacy PDF, literal and pilot routes; revoked
approval cannot reappear after a failed index build; and the full app tests,
Ruff and relevant browser checks pass. Recommended model: GPT-6 Sol / High.
