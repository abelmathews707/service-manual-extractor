# A10 real-manual acceptance — in progress

Updated: 2026-09-27. Branch: `codex/real-manual-acceptance-a10`.
This is a checkpoint, not an A10 pass or a user-facing release claim.

## Verified inputs and isolation

- Extractor A9 `4da6890`, Repair Buddy A8 `6ab7a1e`, and toolkit
  `d150e7d` were checked on clean feature worktrees. The ordinary Repair
  Buddy checkout has unrelated user documentation edits and was not changed.
  The toolkit checkout has an unrelated untracked `-.ppm` and was not changed.
- The preserved normalized GM PDF package passed full original-member hash
  validation: 113 publications, 12,324 page documents, source
  `src_241ae321543b966629942d2b1977d6eb`.
- Ford source C was probed at its recorded `data/incoming/03_F250_F550` path.
  Its exact `content/useni4/v3d.arc` was imported into a new, local-only
  package: one 2003 6.0L diesel PC/ED publication, 152 documents (150 HTML,
  two original PDF pages), no extraction failures. The 2 PDF pages may be
  image-only; no searchable-text claim is made for them.
- A small three-configuration pilot vocabulary was generated from the
  reviewed 2003 Ford and 2006 Silverado source labels. It is deliberately
  not a complete vehicle catalog. The vocabulary generator is
  `acceptance/a10_pilot_vocabulary.py`; derived packages/evidence are outside
  Git under `service-manual-data/a10-acceptance-2026-09-27/`.
- Evidence generation on that pilot vocabulary produced 436 Ford units/537
  assertions and 12,324 GM PDF units/53,876 assertions. Both evidence files
  are tied to the exact normalized sources and pilot vocabulary revision.

## Original-page review and first matching gate

- The native 2006 Silverado 1500 wiring PDF page 1 visibly names its 4.3L
  VIN X engine section. Its page 8 contains the fourth 4.3L engine-performance
  circuit diagram. Page 9 carries the preceding figure's caption and starts
  the 4.8L VIN V section; it has no circuit image of its own. The evidence
  generator marks page 9 `mixed_content` and `metadata_only`, which keeps its
  ambiguous text out of vehicle-scoped search. The diagram and label pages
  need page-pair review before a usable circuit citation can be approved.
- The original cabin-filter PDF page 1 visibly lists model/year groups and
  explicitly excludes 2000 Tahoe Classic and 2000 Yukon Denali. It also states
  a 2003 model-year boundary. OCR text contains those statements; no blanket
  Silverado/Sierra or all-engine approval was made from them.
- With an empty review log and exact make/model/year/engine selectors, the
  combined *in-memory* scope resolver returned 127 confirmed Ford units for
  2003 F-250 6.0L diesel and **zero confirmed GM units** for either 2006
  Silverado 1500 4.3L VIN X or 4.8L VIN V. The GM engine-specific composite
  statements remain proposals, so silently treating them as confirmed would
  be wrong. This is an A10 acceptance gap to resolve by checking and accepting
  exact citations through the review workflow, not by weakening the matcher.

## Open A10 work

1. Review source pages and bind enough precise Ford and GM examples to show
   confirmed, possible, excluded and reference behavior, especially GM 4.3L
   diagrams and the cabin-filter exclusions. Record reviewer, reason and
   exact page evidence; keep page 9 excluded from engine-specific text search.
2. Resume/convert the remaining supported Ford archive instances and GM
   publications, or record a specific pending reason per item. The replacement
   GM HTML path still has not been identified/verified; do not use the old
   damaged USB ZIPs as substitute. Reconcile counts with A1 without counting
   duplicate archive occurrences as new vehicle coverage.
3. Publish a combined immutable library from verified packages and current
   review, build its A9 offline site, and import into a disposable Repair Buddy
   database with the extractor dependency revision pinned. Compare eligible
   IDs/states in both readers and test no cross-make text-shard load.
4. Verify sampled original/derived hashes and citations, inspect tables,
   figures and OCR against originals, measure cold build and warm scoped
   search latency/cancellation/resource bounds, run full tests/Ruff, then
   write the final A10 engineering acceptance report. Keep originals and the
   live database untouched; only consider promotion with a recoverable backup.

The A10 pass criteria and eventual Phase B stopping point remain in
`VEHICLE_MANUAL_APPLICABILITY_PLAN.md`. No Phase B work has started.
