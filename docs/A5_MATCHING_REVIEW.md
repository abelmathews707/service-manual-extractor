# A5 — matching and human review

Status: complete on 2026-09-26 on `codex/applicability-matching-a5`.

## Delivered

- `sme.matching.match_unit` evaluates one cited evidence unit against a
  canonical make/model/model-year/engine selection and optional qualifiers.
  It returns state, reason codes, search eligibility, supporting assertion and
  review event IDs, missing qualifiers and conflicts. It is deterministic;
  there is no similarity score or AI judgment in the decision path.
- Source include alternatives remain correlated. An inherited publication or
  section restriction applies only when the assertion explicitly governs
  descendants. A child exclusion or conflicting child restriction takes
  precedence over a broad parent claim or approval. Unknown make and absent
  sidecars do not enter vehicle-specific search. A metadata-only unit remains
  readable by navigation but cannot enter text search.
- Only an accepted, current `section_applies` review can extend vehicle
  applicability. Pending cross-make leads, shared parts, duplicate content,
  rejected/revoked decisions and stale approvals cannot. A bound review
  cannot silently broaden target configurations or erase its history.
- `sme.review` creates, validates, imports and atomically exports the separate
  append-only review overlay. Proposal, accept, reject, revoke, supersede and
  snapshot rebase preserve exact source evidence bindings. A changed evidence
  or vocabulary revision makes old acceptance stale until a new proposal and
  decision is made. Saving refuses to drop or edit previous events.
- `shared_content_proposals` produces a bounded review queue from explicit
  cross-references, contextual identifiers and exact duplicate text. Each
  lead names its basis, target source/unit and exact target configurations.
  A shared part yields `part_mentioned`; duplicate text yields
  `duplicate_content`; an explicit cross-reference may propose
  `section_applies`. None is accepted automatically.

## Verification

- The frozen A2 decision table's 25 expected state/reason/eligibility cases
  pass. Authored lifecycle tests cover unchanged reimport, changed evidence,
  rejection, revocation, supersession, append-only import/export and stale
  acceptance. A child conflict defeats parent approval.
- A Ford POD v2 fixture was imported, converted to neutral evidence and
  matched: the authored 2003 F-250 6.0L statement confirms the Ford selection
  on its page and excludes the GM selection. A metadata-only unit does not
  become text-search eligible.
- Full extractor suite: 173 tests passed with one opt-in real-OCR test skipped;
  Ruff and `git diff --check` passed. The optional OCR path was exercised in
  A4; A5 did not modify it.

## Boundary and next step

This is a per-unit policy engine and portable decision log, not a multi-source
search index. It does not import material into Repair Buddy or change the
offline viewer. A pending lead is not a fitment claim; the human reviewer must
check the cited original before accepting a specific section/vehicle link.

A6 will assemble several normalized packages with their evidence and review
revision, preserve duplicate book occurrences and original citations, resolve
the eligible unit set **before** search, and export offline scope memberships
and shards. Its gate must show that a Ford 6.0L selection never visits GM 6.0L
text; changing or revoking a review invalidates dependent eligibility and
indexes; and no eligible units never fall back to whole-library search.
Recommended model: GPT-6 Sol / High.
