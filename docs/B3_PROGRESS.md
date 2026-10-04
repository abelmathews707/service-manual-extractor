# B3 — Procedures and diagnostic structure

2026-10-04: B3 implementation is in progress. Native extraction, reviewed reference
bindings and application one-hop traversal are implemented; full B3 acceptance remains pending.
Latest checkpoint: user-supplied PDFs resolve the earlier visual-review blocker.
A real association now has separate engineering readable-reference approvals in
`reviewed-reference-v1`; complete/diagnostic approval remains withheld. See the
final section below before relying on older outstanding-review notes.
Conditional source-reference paths are now represented separately; see the latest
checkpoint at the end. They do not satisfy complete execution-graph acceptance.
Latest scope repair: all seven dependency PDFs (19 pages) were reviewed in the
app checkpoint. The excluded symptom chart was a false positive: an oil-consumption
quantity was counted as an engine. A narrowly tested capture fix and separate
full-source candidate recapture now resolve that cause. The accepted library is
unchanged. A separate candidate library is now built with all old review events
preserved and the two changed-source Ford events explicitly stale. A bound graph
audit now detects missing dependencies and closed cycles, without granting approval.
Complete original-reviewed procedure acceptance remains pending. See the candidate
publication and graph checkpoint below, not historical PDF requests.
Worktree: `/Users/asokmathews/Documents/service-manual-extractor-b3`.
Branch: `codex/procedure-structure-b3`, based on accepted B2
`2945f7c9a73e3d6c87b2f4b160501b35d49955e0`.

Historical 2026-09-28 stop: the five-hour allowance reached 9% remaining; weekly remaining
was 16%. Resume only with sufficient allowance. Preserve the existing stop limits:
approximately 10% five-hour or 5% weekly remaining.

## Verified before stopping

The following is the historical preparation record, superseded by the current
implementation checkpoint below.

- Accepted B2 extractor and app worktrees are clean. Extractor remote matches
  its accepted commit. Repair Buddy remains at `eb368ec5d436debd0a5a12e41f3dec3b5063cbee`
  with its exact B2 dependency pin. No B3 app worktree or dependency change yet.
- The independent toolkit remains at `d150e7d889eb55ebba85065da264ab2bc414755d`
  with the pre-existing untracked `-.ppm` preserved.
- B1 local benchmark and B2 `records-v6` remain under
  `/Users/asokmathews/Documents/service-manual-data/` and outside Git.
- Read B2 acceptance, the structured-evidence contract, B3/B4 plan gates,
  existing record/dependency/quality validators and frozen B1 diagnostic examples.
  No manual re-extraction, new original-layout review or new tests were run.

## Findings and next execution

The existing contract represents ordered steps, tools, warnings, decisions,
branches and references. It checks branch labels, target types, declared vehicle
coverage and transitive quality dependencies. B3 should reuse these contracts.
They validate already loaded records; application source eligibility must still
be resolved before reading each linked unit.

The frozen GM page-87 example explicitly marks prerequisites and its next-page
continuation incomplete. Its Yes/No records cannot establish a complete procedure.
The reviewed V10 page is a reference table, not a reviewed pinpoint procedure.

Resume with a small original-reviewed Ford/GM procedure benchmark and record
the source/target locators and applicability decisions. Implement and test loading
each continuation only after resolving its own vehicle scope. Then extract ordered
instructions, required context and complete branches, integrate reader comparison
and independent quality review, and run the B3 acceptance gate. The proposed
continuation-loading helper was considered but no API or implementation is frozen.

Pass criteria remain in `VEHICLE_MANUAL_APPLICABILITY_PLAN.md`: every evaluated
instruction, reading, warning, condition and branch target matches the original;
required continuations resolve; incomplete or wrong-vehicle paths remain withheld.
Do not invent a branch or claim diagnostic readiness from indexing or schema checks.

Recommended model remains GPT-6 Astra / High. B4 shared web/CLI evidence packets
follow B3; provider integration and semantic evaluation remain later work.

## Current implementation checkpoint — 2026-10-03

`sme/procedure_extract.py` reads bounded native HTML decision tables and native
numbered PDF steps with explicit Yes/No alternatives. It preserves exact branch
wording, instruction context, nested notes and source locators. Missing, duplicate
or merged alternatives abstain. OCR does not silently use the native parser.
Confirmed unit/configuration checks precede HTML parsing; conflicting engines
in a question, instruction or branch cause rejection. Explicit unmapped original
inspection produces no vehicle configuration IDs.

Source hyperlinks are never followed by the extractor. Unreviewed references,
conditional continuations and unordered instruction groups remain incomplete.
`sme/procedure_context.py` adds a single-hop continuation resolver: metadata locates
the target, target-specific vehicle scope is checked before loading, and current
record-bound intended-use quality is checked independently afterward. Excluded
targets load zero text. It is a tested primitive, **not yet wired to application
cross-page traversal**. Loader and quality callbacks must validate current source
and dependency identities; a starting-page approval grants no target approval.

Twelve new authored regression tests pass. The full extractor suite runs 239 tests
with zero failures and two optional Node-dependent skips; Ruff passes.

Local-only root:
`/Users/asokmathews/Documents/service-manual-data/b3-acceptance-2026-10-03`.
Original GM pages 87–89 were rendered and visually inspected. Step 4 distinguishes
VIN W/X pressures; step 6 continues to page 89, which then starts another-engine
procedure. These are retained as review boundaries, not merged instructions.
`expected-fields.json` was entered before extraction; this is agent engineering
comparison, not independent human approval. `records-v2/verification.json` reports
seven Ford and seven GM records with exact compared fields and zero approvals.
The Ford example retains all three destinations in its No branch but remains
unmapped original inspection. Only GM page 87 has existing confirmed applicability;
its prerequisite and next-page targets remain incomplete. Earlier `records-v1`
is historical. Licensed fields, rendered pages and databases stay outside Git.

Repair Buddy's separate `/Users/asokmathews/Documents/repair-buddy-b3` worktree
uses the same branch name. Its reader now presents source steps, decisions and
both branches alongside the original and separate quality state. Existing quality
contracts prevent incomplete instructions from receiving structured approval.
Its tests also caught/fixed a missing-values rendering bug for part references.
The exact extractor is pinned in that application's lock file. Application final
integration results and remaining gates are recorded in its B3 progress document.

## Remaining B3 pass gates

1. Freeze and original-review at least one complete applicable procedure/graph,
   including tools, warnings, prerequisites and every required continuation.
2. Extend bounded ordered-step/tool extraction to separately represented nested and
   conditional alternatives; unsupported instruction groups deliberately remain incomplete.
3. Apply the implemented reviewed-reference bindings and one-hop app traversal to
   the real benchmark. Complete graph expansion/conditional-edge completeness is
   still pending; readable-reference navigation does not satisfy that gate alone.
4. Compare complete graphs and every safety-relevant field against original-reviewed
   expectations; test missing/changed targets, stale/revoked dependencies and excluded
   text loads through the real application path. Retain original reading throughout.

Do not mark B3 complete from the partial examples above. Continue with GPT-6 Astra
/ High. B4 and diagnostic/provider activation remain later work.

## Reviewed-link checkpoint — 2026-10-04

`sme/continuation_review.py` adds explicitly proposed/approved/revoked source-to-target
bindings, exact endpoint hashes, source quotations and reviewed configurations.
Its append-only, revision-checked log is separate from applicability and content
quality. Changed targets cannot silently redirect an approved association. The
target resolver checks its independent confirmed scope before text loading, current
readable-reference quality/dependencies, and the reviewed destination hash.
See [the contract and authoring workflow](CONTINUATION_REVIEW.md).

Repair Buddy now uses that boundary for one-hop reference navigation, rechecking
the starting review before responding. Possible matches, reference-only membership
and unfiltered browsing cannot admit a continuation. Each further click rechecks
eligibility; no recursive expansion means cycles cannot auto-run. The original
reader remains separate and available for explicit comparison. Required tool
context is now included alongside warning context. No real-manual review approvals
were added and diagnostic readiness remains false.

Extractor: 246 tests pass (two optional Node-dependent skips); Ruff passes.
App: 291 tests pass including six real-dependency tests on authored temporary
two-page data; Ruff passes. App-route tests prove excluded targets do not load
original bytes, and revocation during lookup discards the target result. These are
engineering regressions, not the still-pending complete real-procedure comparison.

## Ordered-source checkpoint — 2026-10-04

`sme/ordered_procedure.py` reads explicitly selected native decimal OL/LI sequences,
including split lists with `start`/`value` numbering, and source-quoted required tools.
It refuses gaps, resets, reordered/duplicate recipes, unassigned list content, OCR
and conflicting vehicle restrictions. Only a flat sequence with reviewed recipe
coverage receives next-step edges. Nested lists, conditional/reference language,
unreviewed coverage and unbound figures preserve wording but withhold completeness;
the parser does not invent conditional execution order. Required tools are selected
from the same source; optional/global equipment is not automatically made mandatory.
The region schema additionally permits `text` for plain prerequisite/context blocks.

`acceptance/b3_ordered_extract.py` checks the already confirmed 2003 Ford diesel
`V3D2018.htm` drive-cycle page (`unit_7f9e2dc4e80b9a5215d971cdca9b960c`). Eight
numbered steps and six context records exactly match a separate original-source
transcription, including caution, PTO requirement, temperature, manual-transmission
alternatives and conditional repeat instructions. This is not a V10 source.
All steps remain incomplete because nested/conditional paths and Quick Test require
additional review. No diagnostic edges or quality approvals are manufactured.

Current local-only output is `ordered-records-v2` under the existing B3 acceptance
root, compared with `ordered-expected-v1.json`. `ordered-records-v1` is historical.
The comparison is agent engineering review, not independent human validation.
Eight more authored tests pass; full extractor suite: 254 tests, two optional Node
skips, Ruff clean. Existing GM and Ford decision records remain unchanged.

Next: review/represent nested alternatives and required continuation targets, use
real source/target mappings through the app, and complete the original-reviewed full
procedure/graph gate. Do not label this partial ordered example as B3 completion.

## Nested-source and real candidate checkpoint — 2026-10-04

Explicit opt-in nested extraction now retains parent/child records and composite
labels such as `3.a`, `3.b`, `3.c`. The contract checks reciprocal ownership, exact
child quotations within parent regions, numbering order, source units and cycles.
Parent/child dependencies are bound to quality reviews in both directions. Printed
grouping is not execution order: conditional/transmission alternatives and repeat
paths remain incomplete. The app exposes hierarchy links and ancestor context.

The Ford drive-cycle comparison now includes eight root steps, three separately
recorded substeps and six context records (17 total). Current local-only output:
`nested-records-v3`, using `ordered-expected-v1.json` plus `nested-expected-v1.json`.
`nested-records-v1`/`v2` are historical. Nothing replaces the accepted earlier records.

A real name-to-entry candidate links drive-cycle step 8 to Quick Test `pptQT1`
in `V3D3001.htm`. Both units independently belong to the confirmed diesel scope.
`acceptance/b3_link_candidate.py` compares separately transcribed source markup and
creates only a **proposal** with all comparison/approval checkboxes false. Current
output is `link-candidate-v3`, with `quick-test-expected-v1.json`; there are zero
content-quality or link approvals. The first candidate attempt was rejected before
writing output because of the fuel-heading boundary described below.

Original-layout review is outstanding: the browser blocked opening the local HTML
original. No alternate browser/serving workaround was attempted and no visual review
was claimed. Source-markup comparison is not a substitute for that approval. The
target also retains unresolved OASIS/TSB, modification-reference, QT2/later-step and
instruction-grouping dependencies. It is not a complete diagnostic procedure.

That candidate revealed two scope boundaries: fuel-only context can safely narrow
an already confirmed parent to matching fuel, while rich/negative/unresolved hints
still abstain; a procedure must match **every** declared configuration, not merely
return one matching configuration from the table-row narrower. Authored regressions
cover both. No source applicability event was broadened or automatically approved.
Additional guards reject negative fuel wording (including exclusions and unsupported
fuels) and non-ASCII OL/LI numbers that browsers may not interpret as printed numbers.

Extractor suite: 260 tests, zero failures, two optional Node skips; Ruff passes.
App suite: 293 tests pass with the real extractor fixtures; Ruff passes. Final
real-library HTTP results are recorded in the app B3 handoff after its exact pin
is updated. B3 remains in progress. Next: obtain original-layout review, represent
conditional alternatives/repeat paths, resolve required targets and pass a complete
real-procedure comparison. Recommended model remains GPT-6 Astra / High.

## User-supplied PDF review and real reference acceptance — 2026-10-04

The user saved `Drive Cycles.pdf` and `Powertrain Control Module (PCM) Quick Test.pdf`
in `/Users/asokmathews/Documents/repair-buddy-b3`. All four pages were rendered with
Poppler and visually inspected. They establish the previously missing layout
comparison without retrying or working around the blocked HTML browser URL.
The PDFs remain local, untracked and unchanged; never stage them in Git.

The source's eight root steps, three lettered children and six context records
match the rendered drive-cycle section. Both bullets in its conditional note are
retained. The second page is separate PID/pending-DTC reference material. QT1's
heading, note, eight inspection bullets, question and Yes/No outcomes match its
extracted records. QT2/QT3 are visible but not approved by this bounded review;
QT3's branch table crosses the PDF page break.

`acceptance/b3_review_reference.py` validates a manually declared visual-review
witness, rechecks both endpoints' current confirmed scope before original reads,
checks original hashes/record validity, and creates a **new** acceptance root.
The witness binds exact PDF hashes/pages, bundle revisions and every transitive
endpoint dependency. It is declared agent engineering review, not authenticated
human signoff or an automatic visual-comparison algorithm. The helper cannot
approve diagnostic instructions, production use or vehicle applicability.

Local-only outputs under the existing B3 acceptance root:

- `visual-review-v1.json`: actual comparison findings and frozen identities.
- `reviewed-reference-v1`: unchanged record snapshots, two independent
  `readable_reference` / `engineering` quality approvals, and one association
  approval appended after the original proposal. `link-candidate-v3` is unchanged.
- `app-verification-v6.json`: passed real-library HTTP comparison and isolated
  mutation checks. App handoff records the final pinned rerun separately.

The approved association is a readable reference to the named Quick Test page's
first section. It does **not** establish that rerunning Quick Test requires QT1
as an executable entry point. Historical record snapshots still contain their
old visual-review missing-context label; the separate witness resolves that
specific review but does not rewrite or promote those snapshots. All other
conditional, prerequisite and downstream completeness limitations remain.

The real app route opens exactly the two original endpoints and preserves all
target wording, governing context and both branches. GM/V10 requests load zero
originals. Revoked links and changed source context load zero target originals.
Missing typed targets, changed target context and revoked target quality return
409 with no destination instructions: the eligible target original is read for
validation in those cases, so these are not claimed as zero-read scenarios.
All mutations use temporary copies; accepted reviews are unchanged.

Verification: 268 extractor tests, zero failures, two optional Node skips; 293 app
tests, zero failures; Ruff/diff checks clean. Existing 72 scopes/284,592 memberships,
Ford/GM original readers, V10 reference/diagrams, 23 legacy tables and 280 owner-guide
links remain verified. No product runtime change, live activation, merge or toolkit
change was required for this acceptance checkpoint.

Next B3 work: separately represent the visually confirmed transmission alternatives,
repeat paths and governing conditions. Review QT2/QT3 and each needed external target
with independent scope and quality; unavailable references stay explicit. Pass a
complete real-procedure/graph comparison with no dropped warning, value, qualifier,
instruction or branch before declaring B3 complete. B4 remains later work.
Recommended model: GPT-6 Astra / High (task judgment, not a measured comparison).

## Conditional source paths — 2026-10-04

`source_paths` optionally extends procedure steps with source-quoted alternatives
and repeats, explicit same-unit targets or unresolved reasons. The manufacturer-neutral
`sme.procedure_paths` helper binds reviewed recipes; it does not guess natural-language
logic or execute instructions. The semantic validator rejects invented/detached/ambiguous
quotations, wrong-type/missing/cross-unit or wrong-vehicle targets, duplicate paths,
and claims of complete/unconditional execution. Path sources/targets enter quality
dependency hashes, including bounded self/repeat references.

Reinspection of the user's Drive Cycles PDF confirmed the local-only
`conditional-path-recipe-v1.json`. Eight paths retain the two printed manual-transmission
alternatives and six repeat references. Two targets remain unresolved because the
interrupted/incomplete modes depend on actual execution history. Unqualified base
wording is not silently relabelled as automatic-transmission instructions. The
complete original wording, values, caution, note and PTO requirement remain present.

`acceptance/b3_ordered_extract.py --source-paths <recipe>` now optionally binds those
paths after the existing scope/hash/original-field comparisons. It requires nested
labels and the unchanged visually reviewed PDF hash. Current output is
`conditional-records-v1` under the existing local B3 acceptance root: 17 records,
eight root steps, three substeps, six context records, eight paths, zero approvals.
Use a new output directory, `--nested-expected nested-expected-v1.json`, and the
existing `ordered-expected-v1.json` (absolute paths). The recipe is reviewed source
mapping, not independent proof that the parser can discover arbitrary conditions.

The app's reader and one-hop continuation view display conditional quotations,
source anchors and unresolved targets with explicit non-execution labels. No
condition is evaluated and no path is followed automatically. Prior
`reviewed-reference-v1` remains unchanged and valid only for its old snapshots;
its content review and association both resolve **stale** against the newly
enriched source. No approvals were copied into the new records.

Verification: 277 extractor tests, zero failures, two optional Node skips; 295 app
tests including real extractor fixtures, zero failures. Ruff/diff checks clean.
The app's final pinned real-library check is recorded in its progress document.
No source/PDF edits, live activation, merge or toolkit changes.

Remaining B3 at that checkpoint: review/extract QT2/QT3 and independently resolve required continuations;
establish complete branch coverage and compare at least one complete applicable real
procedure/graph. The present paths are inspectable reference structure, not approved
execution edges, exhaustive alternative coverage or finished B3. B4 and AI/provider
activation remain later work. Continue with GPT-6 Astra / High.

## Quick Test sections and reference inventory — 2026-10-04

QT1, QT2 and QT3 are now extracted together into a single independently scoped
source-unit bundle. `extract_html_decisions` accepts an explicit bounded list of
anchors, retains separate questions/context/Yes-No branches and rejects missing,
duplicate or overlapping sections. The single-section extractor also inventories
references inside instruction groups/notes, previously reported only as missing
context. Original hrefs and governing wording are retained without opening targets.
Exact same-document fragments can identify candidate decision records, but never
become approved associations, execution edges or complete diagnostic instructions.

`acceptance/b3_quick_test.py` compares extraction with a separately transcribed,
local-only expectation and SHA-bound PDF inspection witness. Both pages of the
user-supplied Quick Test PDF were visually checked, including QT3's question on
page one and its Yes/No table on page two. The helper does not perform visual
inspection itself or grant approval. Source applicability is confirmed before
PDF/original reads. Destination classification uses existing metadata only.

Local output under `b3-acceptance-2026-10-03/quick-test-records-v1` contains:

- 21 records, three decision sections and all six printed branch answers;
- nine hyperlink occurrences: two same-page candidate destinations and seven
  distinct other pages, all independently confirmed for the selected Ford diesel
  in the current index; destination content quality is still unreviewed;
- all original preparation instructions, conditional wording, scan-tool references,
  notes and recorded-data requirements preserved in instruction/context groups;
- zero destination-original reads, quality approvals or association approvals.

`quick-test-all-expected-v1.json`, `reference-inventory.json` and the detailed
`quick-test-verification.json` remain outside Git, with licensed source wording.
OASIS/TSB material is still an unresolved named dependency, not a discovered link.
Grouping/tools/conditional execution and full prerequisite coverage are unapproved.
The older reviewed-reference and conditional-step snapshots are unchanged; existing
approvals have not been transferred to these newly extracted records.

Verification: 286 extractor tests passed with two optional Node skips; Ruff and
diff checks clean. Added regressions cover all selected sections, context references,
exact branch comparison, invalid/missing targets, independent destination metadata
and scope denial before original reads. The app's new `--quick-test-records` option
checks all structured cards and source wording, no destination traversal, and
zero-original-read rejection for GM and gasoline V10. See its B3 progress document
for final exact-pin full-library verification. No original/PDF edits, live activation,
merge, release or toolkit change.

Next B3 checkpoint: independently review the seven destination pages and their
required context; bind only justified associations, with content quality approved
separately. Convert instruction groups/alternatives into reviewed source structure
without guessing execution order. Then compare a complete applicable real procedure
and every conditional branch with the originals, retaining incomplete abstention
where a target or external prerequisite is unavailable. B3 remains incomplete;
B4 shared web/CLI evidence packets and AI/provider activation remain later work.
Recommended development model remains GPT-6 Astra / High (task judgment, not a
measured model comparison). Preserve the reported-usage stop thresholds.

## One-hop dependency audit — 2026-10-04

`acceptance/b3_dependency_audit.py` now performs a bounded structural inspection of
the Quick Test original and its seven direct reference pages. Each unit must have
its own current confirmed eligibility before original bytes are read; bytes must
match the preserved original hash before parsing. Duplicate targets are read once,
fragment existence is reported without approving an association, and deeper links
are metadata-only. Missing, unconfirmed, external and unsupported destinations
remain explicit. No source HTML/scripts are executed and no figures are loaded.

The local-only `quick-test-dependencies-v1/dependency-audit.json` under the B3 root
preserves eight parsed documents, including complete visible text, static table
structure, image references and source hashes. Seven direct target pages were read;
176 downstream href occurrences (87 distinct href strings) were inventoried, with
zero recursive reads and zero approvals. These are links, not 176 additional manuals
or required test steps. Context and visual completeness remain unreviewed.

Findings from source markup/text inspection:

- The engine-control overview includes a specific modifications subsection and a
  non-hyperlinked reference to the vehicle warranty guide.
- Pinpoint Test AE's direct target is an introduction with entry restrictions,
  connector-handling cautions/notes and images, not the actual test sequence. Its
  two onward links name the same separate test page.
- Scan-tool hookup requires manufacturer-specific cables/adapters/instructions,
  records communication-error prerequisites and links back to AE.
- Quick Test Description distinguishes five test modes, mode-specific conditions
  and an image. These cannot be flattened into one universal instruction list.
- Freeze Frame Data has a PID/unit table, data-retention behavior and external
  scan-tool instructions. It is not a complete diagnostic procedure.
- The DTC routing table has 133 href occurrences (71 distinct hrefs), merged
  headers separating test modes, and lettered footnotes. One href is a legacy
  query-dependent ASP frameset reference, currently unsupported. The 132 other
  occurrences resolve to independently confirmed unit metadata, not reviewed
  content or verified destination fragments.
- The symptom index has 40 occurrences to 15 chart anchors in `V3D3003.htm`.
  Its target unit `unit_bde3920ebcf95f609fa39db93e0e6758` is absent from the current
  selected confirmed eligibility set; no target original was read. The audit's
  `excluded` fallback means outside this search scope, not proof of an explicit
  wrong-vehicle verdict. Reconcile applicability separately; do not inherit the
  index page's eligibility or change the review to force a match.

Seven authored regression tests cover zero-read source/target denial, changed
originals before parsing, missing metadata, deduplication/cycles, target budget,
table/image-reference retention and missing fragments. Full gate: 293 extractor
tests, two optional skips, zero failures; Ruff and diff checks pass.

Visual approval is blocked: only the prior Drive Cycles and Quick Test PDFs are
present in the B3 folders. The seven target pages need user-supplied PDF copies
for original-layout comparison. Do not work around the earlier browser URL-policy
denial by another browser/indirect server. Repair Buddy's latest B3 progress section
has direct original-file links and requested PDF filenames. No new readable-reference,
association, applicability, diagnostic or production approval was granted. No
runtime extractor behavior, live data, original manuals or toolkit changes.

Next: obtain those rendered originals, inspect every relevant page/table/figure,
preserve governing context, and reconcile the symptom-chart eligibility separately.
Approve only exact supported readable associations/content; full diagnostic graph
acceptance remains open and must not require blindly expanding all 176 links.
Choose a bounded applicable path with complete prerequisites and branches for the
real-procedure benchmark. B4 and AI/provider activation remain deferred.

## Symptom-chart false-positive repair - 2026-10-04

Metadata-only matching established that `V3D3003.htm` is excluded for
`mixed_content`, not a wrong-make/model/year verdict. Its publication has explicit
2003 F-250 6.0L diesel evidence. A separate, hash-checked administrative source
inspection (not selected diagnostic retrieval) found two litre mentions: the
engine heading and an oil-consumption threshold. The old displacement expression
misread the decimal threshold as a two-digit suffix, then treated it as a second
engine. No user-selected search or diagnostic packet was broadened during inspection.

`sme/evidence.py` now reads full decimals without starting inside a number. It
discounts only a tightly bounded oil-consumption comparison with an immediately
adjacent quart conversion. An oil keyword alone, a conversion alone, unknown
quantities and actual other-engine wording cannot clear the mixed-content guard.
This is not a general physical-quantity classifier or an applicability approval.
The existing engine/unit-spelling scope is retained rather than expanded here.

`acceptance/b3_symptom_scope.py` validates the current metadata/review snapshots,
rehashes the preserved Ford originals, captures a new evidence snapshot and checks
that unit identities, originals and applicability assertions are unchanged. It
never publishes a library or copies old quality/association approvals. Candidate
matching uses fresh evidence without an old review overlay.

Final local output: `b3-acceptance-2026-10-03/mixed-content-recapture-v2`.
Candidate evidence revision:
`017261d33e5c6ce0cba33aab07d0cc1373c652db8dbd7ddb3e62ae534a5da967`.
Only eleven unit flags across two source documents change: `V3D3003.htm` and
`V4C3003.htm`. Both have the same bounded oil-quantity issue; this is not eleven
manuals. No newly mixed units appear in the final capture. The earlier v1 output
is a superseded broader experiment, NOT the approved candidate for follow-up.

For the target symptom chart, fresh candidate matching confirms the Ford diesel
fixture and excludes gasoline V10, CNG V10 and all three GM fixtures. The original
saved library still excludes it: sidecars are immutable, and changing capture
code cannot update existing search shards or silently reactivate old approvals.
No original/PDF, existing library, review event, live database or toolkit was edited.

Fourteen new authored tests cover decimal parsing, narrow quantity context,
genuine mixed engines, candidate identity and stale/tampered snapshots, unchanged
applicability statements and other-vehicle exclusion. Full extractor gate: 307
tests, two optional skips, zero failures; Ruff and diff checks pass. App exact-pin
verification is recorded in its scope-repair checkpoint.

Next: publish a separate disposable candidate library, preserving historical
review events and making changed-source approvals explicitly stale. Re-review
only exact supported bindings; do not copy approval to a new evidence revision.
Verify new eligibility/shards and old Ford/GM/V10 boundaries before using the
chart in selected retrieval. Then inventory a bounded chart path and retain all
required prerequisites and branches for original-layout/complete-graph comparison.
No additional PDF request is made by this checkpoint. B3 remains incomplete.
Recommended development model remains GPT-6 Astra / High; B4 remains later work.

## Candidate publication and graph audit — 2026-10-04

`acceptance/b3_publish_candidate.py` publishes only to a new disposable directory.
The real `candidate-library-v1` generation is
`88c2c1548b715681f1899c633066124e50f53c640b1a7226f912bdc0127be48d`, with six packages,
72 scopes and 850 shards. All eight previous applicability events are preserved;
the two Ford events are stale against the changed Ford evidence revision. The old
snapshot is retained in `evidence-history.json`. No review event was added, no
content-quality or link approval was transferred, and the accepted library was
not replaced. **The candidate is not a deployment replacement:** its V10 reference
page is deliberately withheld until its exact binding receives a new review.

`search-read-verification-v2.json` independently reruns search on the actual new
generation. Before each shard's bytes are read, metadata must admit every unit
and exclude the opposite manufacturer. Diesel reads five allowed shards; each
of the three GM fixtures reads one; V10 and CNG read zero. Only the diesel fixture
admits the repaired symptom chart. Seven authored publication regressions include
wrong-brand requests, mixed shards, same-brand wrong-scope content, wrong-engine
admission and an existing-output overwrite guard. The helper now also checks the
baseline pointer/review bytes before and after any subsequent publication run;
the first build's historical report predates that explicit byte-comparison check.

`sme/procedure_graph.py` adds a bound-dependency structural assessment. It checks
required branches, incomplete context/tools/targets, reference-only conditional
paths, unsupported nested execution order, and whether each represented flow
component has an explicit reachable terminal. Closed cycles are incomplete;
cycles with an explicit exit are retained without executing/evaluating conditions.
The quality validator uses the same assessment before accepting structured or
diagnostic instruction reviews. Readable-reference approvals remain separate.
The assessment is **not** proof that the original has been completely extracted,
a termination guarantee for real vehicles, or any diagnostic approval.

Nine authored graph regressions pass, including missing alternatives, incomplete
tools/outcomes, closed loops, repeats with exits and independent quality gates.
Full extractor suite: **323 tests, zero failures, two optional skips**; Ruff passes.
Repair Buddy exposes the assessment alongside each procedure/decision and in the
one-hop reader, with explicit limitations and no extra original reads.

Full real-procedure acceptance remains open. The Ford symptom page contains
fifteen routing charts, not a self-contained diagnostic procedure. The original
GM page-87 example still requires its system check, coil test, next-page steps,
VIN-specific readings and external failure destinations. None may be discarded
or relabeled a successful terminal merely to pass B3. Existing bounded original
comparisons remain valid historical evidence; no diagnostic/provider activation
or B4 work has begun.
