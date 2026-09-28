# B1 — V10 scope and structured-evidence checkpoint

Date: 2026-09-28. Status: contracts and original-source engineering acceptance
implemented; final Repair Buddy integration verification is in progress.
Branch: `codex/structured-evidence-b1`, based on accepted plan commit
`b3043a79b913f6302428fcb815f5565f8f3c4c50`.
Worktree: `/Users/asokmathews/Documents/service-manual-extractor-b1`.
The owner authorized beginning B1 while retaining the five-hour usage stop
threshold of approximately 10% remaining. This is a resumable discovery
checkpoint. Current engineering review is bounded reading applicability, not
production approval or diagnostic validation.

## Current implementation (read before the historical discovery notes)

- Added all nine typed-record shapes and an independent, purpose-specific
  quality log. See [the contract](STRUCTURED_EVIDENCE_CONTRACT.md).
- Added a source-backed 2003 F-250 gasoline 6.8L V10 / 4R100 / 4WD configuration,
  retaining every A10 configuration. VIN S gasoline and VIN Z natural-gas engines
  are distinct, even though both have 6.8L displacement. The user's qualifiers
  remain declared configuration, not proof from an actual decoded VIN.
- Reviewed the original V32 catalog, reference-values page, and workshop
  identification-code tables. Exact V10 reading acceptance binds the page's
  native heading and its original catalog model/year/gasoline entry; no book-wide
  acceptance or numeric diagnostic approval was added.
- Fixed configuration approval lookup to respect transmission/drivetrain.
  Combining a reviewed native HTML heading with original catalog identity requires
  a current exact-unit acceptance and the actual bound ancestral statements;
  filenames, OCR and unrelated pages cannot fill those missing fields.
- Re-captured applicability sidecars from all six immutable A10 packages, checking
  original hashes without re-extracting or redoing OCR. Published a separate
  disposable library; old A10 outputs and the live application database are intact.
- Original-layout-reviewed local ground truth covers 16 records, all nine types
  and 25 scenarios. Eight scenarios are held out. Boundary, abstention, field,
  staleness, revocation and source-resolution checks pass. Two held-out V10
  natural-language queries remain literal-search misses; do not claim all future
  retrieval targets are met or tune query expansion to conceal these misses.
- Current extractor verification: 216 tests pass with two optional-environment
  skips; Ruff passes. A10 Ford diesel, all three GM scopes, OCR possible/excluded
  states, generic-reference opt-in, cancellation and stale-review rejection pass.

Local-only acceptance root:
`/Users/asokmathews/Documents/service-manual-data/b1-acceptance-2026-09-28`.
Generation: `library/generations/30ef410f2c567f94e8e4af4a288b9863906fb46ce5f84a4ca9d20dc404093e2c`.
The authoritative current benchmark report is `verification-v2.json`; v1 is
historical. Golden source quotations are in `ground-truth.json`; records and
quality log are in `structured-records.json` and `structured-quality-review.json`.
No licensed manual content, renderings, database or local config enters Git.

Remaining before B1 closes: commit/push the extractor, pin it in the independent
Repair Buddy B1 worktree, import only a new disposable database, and verify the
saved V10 pilot, reader/diagram links, wrong-vehicle rejection and existing app
regressions. Then record the integration results and update the plan status.
Do not begin B2, merge, release or activate the live database in this task.

## Explicit coverage / approval limits

The no-start concern is a feasibility benchmark, not a diagnosis. CKP reference
readings are available, but complete eligible pinpoint/no-start instructions,
exact V10 wiring context and remaining workshop applicability still require
review. Ask about normal cranking, DTCs/live readings and actual VIN/qualifiers;
never substitute GM, diesel or CNG material. A revision date does not change the
publication's model year. The no-load note governs the generic OBD II table, not
every sensor/input table on the page. GM page 87 contains an illustrative test
figure and only part of a procedure; its following page and prerequisites are
not approved. OCR cabin-filter content remains possible for 2002 and excluded
for 2006. B1 creates **zero production diagnostic approvals**.

## Historical first discovery checkpoint

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

Further original-HTML inspection identifies this as a diagnostic reference
values table, not an ordered pinpoint test. It uses merged headers with separate
operating-condition columns (KOEO, hot idle and two vehicle speeds), a PCM
pin/PID column, and combined measurement/unit expressions. B1 should use it
as a candidate for qualified specification records and table-region anchors:
each value must inherit its sensor, pin/PID, condition and unit context. A
flattened cell or fragment cannot supply those relationships by itself.
The page displays a procedure revision date of 2004-09-23 despite residing in
the 2003 source collection. That date is a revision date, not proof of model
year coverage; verify publication/catalog identity separately. Its image
`A0051363.gif` also needs original figure review. No numeric values from this
candidate have been promoted into approved records.

## Original resume sequence (contracts/source benchmark now implemented)

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

At the first discovery checkpoint no schema, validator, vocabulary expansion,
new review approval, test benchmark or pilot activation had been implemented.
The current implementation above supersedes that historical status. Continue
the remaining B1 integration check, not B2.

## Checkpoint verification

Original citation exists; its title and byte hash were checked. Candidate
discovery ran against the disposable database with read-only SQLite access.
Documentation link/diff checks are appropriate for this checkpoint; runtime
tests are required when contracts or scope behavior are implemented. All manual
text and detailed source files stay local and outside Git.
