# B3 — Procedures and diagnostic structure

2026-10-03: B3 implementation is in progress. The first extraction and continuation
boundary checkpoint is implemented; full B3 acceptance remains pending.
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
2. Extract explicit ordered steps/tools and distinguish conditional alternatives;
   current HTML instruction groups deliberately require further review.
3. Persist reviewed cross-page/manual target bindings, integrate scoped traversal
   using the resolver, and handle bounded expansion/cycles without dropped branches.
4. Compare complete graphs and every safety-relevant field against original-reviewed
   expectations; test missing/changed targets, stale/revoked dependencies and excluded
   text loads through the real application path. Retain original reading throughout.

Do not mark B3 complete from the partial examples above. Continue with GPT-6 Astra
/ High. B4 and diagnostic/provider activation remain later work.
