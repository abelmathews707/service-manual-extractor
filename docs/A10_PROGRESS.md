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
- A small four-configuration pilot vocabulary was generated from the
  reviewed 2003 Ford, 2002 Silverado, and 2006 Silverado source labels. It is deliberately
  not a complete vehicle catalog. The vocabulary generator is
  `acceptance/a10_pilot_vocabulary.py`; derived packages/evidence are outside
  Git under `service-manual-data/a10-acceptance-2026-09-27/`.
- Evidence generation on that pilot vocabulary produced 436 Ford units/537
  assertions and 12,324 GM PDF units/53,876 assertions. Both evidence files
  are tied to the exact normalized sources and pilot vocabulary revision.

## Original-page review and first matching gate

- The native 2006 Silverado 1500 wiring PDF page 2 contains a 4.3L VIN X
  circuit diagram with its caption on page 3. Page 9 carries the preceding
  figure's caption and starts the 4.8L VIN V section; it has no circuit image
  of its own. Page 10 contains a 4.8L VIN V diagram with caption on page 11.
  Page 9 remains `mixed_content` and `metadata_only`, so it cannot enter an
  engine-specific text search. The 2002 Silverado engine-performance PDF page
  87 contains a native-text 4.3L VIN W/X fuel-injector balance procedure.
- Original GM PDFs sometimes switch engine headings between pages. An earlier
  normalization inherited the first-page heading as every page's title, which
  could falsely suggest a 4.3L page where the original says 4.8L. PDF page
  titles now use the source filename and page number; unit evidence uses only
  page-specific text. The old derived package remains as historical input;
  the fresh `gm-pdf-safe-titles` package and v2 evidence are the acceptance
  inputs. No production review was inherited from the earlier package.
- The original cabin-filter PDF page 1 visibly lists model/year groups and
  explicitly excludes 2000 Tahoe Classic and 2000 Yukon Denali. It also states
  a 2003 model-year boundary. OCR text contains those statements; no blanket
  Silverado/Sierra or all-engine approval was made from them.
- An agent-reviewed **disposable pilot**, not production approval, binds
  native page/caption citations for GM pages 2, 10 and 87 to three exact
  Silverado configurations. The matching rule permits an accepted, adjacent
  PDF caption to fill an otherwise missing engine qualifier, but not to
  override exclusions or approve a mixed/metadata-only page. Regression tests
  cover those boundaries.
- The combined pilot export contains one Ford publication and all 113 GM PDF
  publications (114 total), 52 scopes, 183 text shards and 11,496 searchable
  units in the offline site. Reproducible local-only inputs and outputs are
  under `service-manual-data/a10-acceptance-2026-09-27/`: `pilot-review-v2.json`,
  `pilot-library-v2`, `pilot-site-v2`, and `pilot-verification-v2.json`.
  Its library revision is `07ae1fdfa4d0874530adfa39f9dcb607d02d49cbc2865599d0c3341e0ee90484`;
  review revision is `4d32c54c129234dc1521f06d529afbad6c5713a5c6fe3dc8bac17f8fcc92ed11`.
- The published search gate and a browser walkthrough both returned 127
  eligible Ford sections, only cited GM page 87 for 2002 VIN W, only page 2
  for 2006 VIN X, and only page 10 for 2006 VIN V. No other-make text shard
  was loaded. Opted-in reference material, cancellation, stale-review
  rejection and the original-PDF page-87 link passed. The measured warm GM
  p95 of about 0.12 ms concerns a **single reviewed section**; it is not a
  full-library performance claim.

## Open A10 work

1. Expand source review to possible, excluded and OCR examples, especially
   the cabin-filter exclusions. Record reviewer, reason and exact page
   evidence; keep page 9 excluded from engine-specific text search. The
   current agent-reviewed events are a pilot, not a claim of human approval.
2. Resume/convert the remaining supported Ford archive instances and GM
   publications, or record a specific pending reason per item. The replacement
   GM HTML path still has not been identified/verified; do not use the old
   damaged USB ZIPs as substitute. Reconcile counts with A1 without counting
   duplicate archive occurrences as new vehicle coverage.
3. Extend the already-published pilot library with the remaining Ford imports,
   then import into a disposable Repair Buddy database with the extractor
   dependency revision pinned. Compare eligible IDs/states in both readers
   and test no cross-make text-shard load.
4. Verify sampled original/derived hashes and citations, inspect tables,
   figures and OCR against originals, measure cold build and warm scoped
   search latency/cancellation/resource bounds, run full tests/Ruff, then
   write the final A10 engineering acceptance report. Keep originals and the
   live database untouched; only consider promotion with a recoverable backup.

The A10 pass criteria and eventual Phase B stopping point remain in
`VEHICLE_MANUAL_APPLICABILITY_PLAN.md`. No Phase B work has started.
