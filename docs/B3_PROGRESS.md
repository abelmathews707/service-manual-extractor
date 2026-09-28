# B3 — Procedures and diagnostic structure

2026-09-28: selected by the owner; preparation only. Implementation has not started.
Worktree: `/Users/asokmathews/Documents/service-manual-extractor-b3`.
Branch: `codex/procedure-structure-b3`, based on accepted B2
`2945f7c9a73e3d6c87b2f4b160501b35d49955e0`.

Stopped because the five-hour allowance reached 9% remaining; weekly remaining
was 16%. Resume only with sufficient allowance. Preserve the existing stop limits:
approximately 10% five-hour or 5% weekly remaining.

## Verified before stopping

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
