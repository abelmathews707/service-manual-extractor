# B2 — Specifications and part references

Date: 2026-09-28. Status: complete within bounded engineering acceptance.
B3 has not started. Both repositories use `codex/structured-specifications-b2`;
changes are committed and pushed, not merged or activated in the live database.
Extractor worktree: `/Users/asokmathews/Documents/service-manual-extractor-b2`.
Application worktree: `/Users/asokmathews/Documents/repair-buddy-b2`.
The application lock file pins the exact independently versioned extractor HEAD.
Stop ongoing work at approximately 10% five-hour remaining or 5% weekly remaining.

## Implemented

`sme/structured_extract.py` uses explicit structural recipes, not expected numeric
answers. It expands row/column spans, binds each value to its original header and
unit, retains original wording and governing context, and never borrows notes
from another table. A row can narrow its confirmed parent vehicle scope, never
broaden it; conflicting brands/engines and unresolved explicit restrictions
abstain. Code/dependency fingerprints participate in extraction identity so a
changed implementation cannot silently inherit an earlier quality approval.

Missing, composite, footnoted, unsupported and OCR values abstain or remain
ambiguous. Zero remains distinct from missing. No unit conversion, OCR repair or
numeric inference is performed. Native PDF regions reject clipped words and
ambiguous whole-region grammar; conditions absent from a region remain ambiguous.
Printed identifiers are only mentions in a declared namespace, never inferred
fitment or supersession. Unmapped mentions require explicit original review.

Repair Buddy optionally reads per-unit typed files **after** its existing vehicle
eligibility check. It verifies the exact clean dependency pin, original/library
identity, evidence/vocabulary revisions and source wording. No global typed-text
index is searched. The reader displays values, units, conditions, source locators,
governing headers/notes and both applicability and content-quality reasons beside
the original. Missing/stale extraction does not disable checked original reading.
Part mentions link to the separate vehicle/shared-content review queue.

Named-use quality decisions have signed preview/confirmation, independent local
logs, serialized writes and fresh scope/record checks. Readable-reference and
structured-reference quality are separate. This is declared **engineering** review
only, not authenticated production signoff. No diagnostic-instruction approval,
automatic quality approval, fitment inference or vehicle-review change is issued.

## Verification and local evidence

Local-only root:
`/Users/asokmathews/Documents/service-manual-data/b2-acceptance-2026-09-28`.
`recipes.json` contains structural rules; `records-v6/verification.json` is the
final extraction report. Earlier versions remain historical and are not active.
Licensed values, manual quotations, gold files, originals, images and databases
remain outside Git.

- Nine records across two Ford units: three specification records with ten
  readings, four governing context records, and two printed part mentions.
- Three frozen B1 gold comparisons pass exactly. One additional held-out MAF
  voltage row passes exact field/condition comparison, distinct from the generic
  MAF flow row. Its expected fields were entered from the original before that
  row's extraction; this is agent engineering evidence, not independent human
  or blind third-party validation.
- The GM native-PDF illustration abstains: a sample test/pressure example is not
  a universal specification. No positive GM typed-specification coverage is
  claimed. Its original remains readable through existing scope rules.
- Unmapped Ford workshop part mentions carry no vehicle configuration IDs and
  cannot enter the selected gasoline V10 path.
- Extractor: 227 tests run, zero failures, two optional Node-dependent skips.
  Ruff passes. Authored tests cover spans, zero/missing, units, conditions,
  context boundaries, OCR, namespaces and matching/conflicting row restrictions.
- Application: 275 tests pass; Ruff passes. Tests include wrong-vehicle rejection
  before the typed loader, stale-reader fallback, signed tokens, preview/commit
  races and vehicle-review changes. Disposable integration verifies saved
  proposals/approvals, fresh reload, dependency staleness, revocation and CNG
  rejection. Test approval identity is agent/engineering only.
- B1 regressions retain 72 scopes and 284,592 memberships, 23 unchanged legacy
  tables and 280 checked owner-guide links. The live database, accepted B1/A10
  worktrees, independent toolkit and main-checkout user edits are preserved.

The application acceptance report is `app-verification-v2.json` under the local
root. Its scratch review files are separate from the unapproved candidate files.
The reader was also checked locally against the original Ford table/diagram.
Automated checks are not a full mobile/accessibility audit or a mechanic's review.

## Limits and next step

This is bounded recipe-driven extraction, not a general parser for every table or
bulk processing of the manual library. Native-PDF positive specifications, OCR
tables, full V10 procedure/wiring coverage and replacement GM HTML acceptance
still need their own reviewed examples. Two frozen B1 literal-search paraphrases
still miss; no query tuning or semantic/provider integration was added here.
Current packets remain `diagnostic_ready: false`.

Next is **B3 — procedures and diagnostic structure**, only when selected. First
freeze a small original-reviewed Ford/GM benchmark with prerequisites, tools,
warnings, ordered steps, readings and complete Yes/No paths. Extract those as
linked records with original locators, including reviewed cross-page/manual
continuations. Show the interpreted steps beside the originals. Recheck vehicle
eligibility and intended-use quality independently for every target; a valid
starting page cannot admit an excluded continuation. Persist context decisions
and invalidate approvals when any governing dependency changes.

Pass: every evaluated safety-relevant value, instruction, condition, warning and
branch target matches its original; every required branch and continuation is
present and resolves. Missing or ambiguous structure stays incomplete/unapproved;
wrong-brand/engine continuations load zero forbidden text. Keep original reading
available and run Ford/GM, review-staleness and scope regressions. No invented
branches or automatic diagnostic approval. B4 shared AI/CLI packets remain later.

Recommended development model: **GPT-6 Astra / High**, for cross-page structure,
branch reasoning and safety/completeness review. This is a workload-based judgment,
not an extractor runtime dependency or a guarantee about credit consumption.
