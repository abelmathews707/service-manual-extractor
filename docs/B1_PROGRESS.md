# B1 — V10 scope and structured-evidence checkpoint

Date: 2026-09-28. Status: started; **B1 is not complete**.
Branch: `codex/structured-evidence-b1`, based on accepted plan commit
`b3043a79b913f6302428fcb815f5565f8f3c4c50`.
Worktree: `/Users/asokmathews/Documents/service-manual-extractor-b1`.
The owner authorized beginning B1 while retaining the five-hour usage stop
threshold of approximately 10% remaining. This is a resumable discovery
checkpoint, not V10 applicability approval or diagnostic validation.

## Verified starting state

- Both A10 feature worktrees were clean. Repair Buddy's extractor pin matches
  the plan revision above. Its pilot remains the 2003 F-250 6.8L V10, 4WD,
  automatic, with `4R100` in the saved manifest; those qualifiers require source
  verification before the reviewed-library path can use the fixture.
- The A10 vocabulary generator intentionally includes only the diesel Ford
  and three Chevrolet configurations. V10 mappings have not been added.
- B1 uses a separate branch/worktree so the accepted A10 dependency remains
  usable at its pinned revision. Toolkit and ordinary main checkouts remain
  independently versioned; no application or source files were modified.
- Inspection used the existing disposable database in SQLite read-only mode:
  `/Users/asokmathews/Documents/service-manual-data/a10-acceptance-2026-09-27/repair-buddy-full-disposable-v2.sqlite3`.

## Candidate material already available

Restricted discovery to `03_F250_F550` source identities. A literal `6.8L`
search of its existing normalized evidence found the following candidate counts:

| Publication role | Evidence units containing the literal |
| --- | --- |
| Wiring / E3O | 24 |
| Diagnostics / On Board Diagnostics | 320 |
| Workshop / S3O | 967 |

These are evidence-unit counts, not unique pages, procedures, approved matches
or complete V10 coverage. Several units can share one original citation.
Mixed-engine content and incidental mentions still require review. No new
extraction/OCR or inference from GM content was needed to locate candidates.

One concrete original HTML candidate is:

- Source-relative citation: `originals/content/useni4/v32/V326065.htm`.
- Source heading/meta title: `6.8L E/F-Series (A/T)`.
- Example current unit: `unit_3008381669b17b268a5bdf6e5c1e3338`.
- Original HTML SHA-256:
  `20f3a62c0efb61105d18f9af9d8c51a60c9a8f77a993651a9314830cd7e33442`.
- Package: `0002-src_7c2747f1e143b7a36697aae0f9f68f45` in generation
  `d68c771ea3fea5b12d0e84fe9b2585abf56fbdff62a4d8fcc357271146e00ec2`,
  beneath the existing `full-library-v2/generations/` local root.

The original bytes and heading were inspected as text. The page has not yet
received visual/table/diagram review or independent diagnostic approval. Its
heading supports a 6.8L automatic-transmission candidate; it does not by itself
establish exact model, model year, fuel, drivetrain or transmission identity.
Other diagnostic candidate citations include `V321020.htm`, `V321022.htm` and
`V323003.htm` under the same source-relative `v32` directory; these remain
unreviewed. Do not approve an entire publication from these mentions.

## Resume B1 in this order

1. Read the revised B1 gate in
   [the authoritative plan](VEHICLE_MANUAL_APPLICABILITY_PLAN.md). Inspect
   original V32 pages alongside their catalog, workshop and wiring context.
   Establish the exact V10 tuple and required qualifiers; retain unresolved
   restrictions and explicit missing coverage. Keep diesel/GM exclusion cases.
2. Define canonical V10 vocabulary and precise source-backed applicability
   evidence using the frozen contracts. Build a separate local review/library
   generation for acceptance; do not rewrite A10's immutable outputs or live DB.
3. Define versioned typed-record and independent quality/completeness review
   contracts. Preserve original wording, locators, units/conditions, warnings,
   prerequisites, branch edges, intended use and dependency hashes. Existing
   applicability approval must not imply diagnostic-quality approval.
4. Establish the independently reviewed 15–25-scenario benchmark across native
   HTML/Ford tables/native PDF/OCR PDF, with held-out examples, wrong-engine
   and cross-brand competitors, missing context and expected abstentions.
5. Implement schema/semantic validation and meaningful positive/negative gates.
   Verify V10 positive results and excluded-text boundaries; preserve Phase A
   behavior. Bind the app pilot only after its reviewed scope passes.

No schema, validator, vocabulary expansion, new review approval, test benchmark
or pilot activation has been implemented at this checkpoint. Continue **B1**,
not B2. Its recommended development model remains **GPT-6 Sol / High**.

## Checkpoint verification

Original citation exists; its title and byte hash were checked. Candidate
discovery ran against the disposable database with read-only SQLite access.
Documentation link/diff checks are appropriate for this checkpoint; runtime
tests are required when contracts or scope behavior are implemented. All manual
text and detailed source files stay local and outside Git.
