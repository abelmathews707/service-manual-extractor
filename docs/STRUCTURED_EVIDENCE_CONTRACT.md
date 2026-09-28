# Structured evidence and independent quality review — B1

These contracts extend the Phase A library/matcher, not replace it. They do not
extract manuals, call an AI provider, grant fitment, or approve a diagnosis.
The schemas and `sme.structured_contracts` work without optional dependencies.
JSON Schema checks shape; semantic validation checks hashes, source bindings,
conditions, relationships, branch labels and review transitions.

## Records and locators

`structured-evidence/v1` contains a revision and typed records. Every record has
a stable identity, content hash, source identity/hash, immutable generation and
normalized-content hashes, applicability evidence revision, original unit and
document identities, original-file hash, source citation, provenance and an
extraction-version label. Applicability names the exact vocabulary and policy
revision and a finite list of configuration IDs. An empty list means no vehicle
mapping has been established; it never means all vehicles.

The locator is a contextual exact quotation, an HTML selector, or a PDF page
and normalized `[left, top, right, bottom]` rectangle. The citation still opens
the original file/page. `original_text` preserves source wording; normalized
whitespace is allowed for text matching, not changed numbers or terminology.
HTML/PDF spatial locators also need visual comparison with the original, not
just a string match. Reference captions are not evidence that every number in
an image was read correctly.

| Type | Required payload | Important boundary |
| --- | --- | --- |
| Specification | Subject, quantity, condition-bound original values/units; optional normalized ranges/units | A missing normalized value is absent, not zero. Never separate a number from its headers/notes. |
| Part reference | Original identifier, namespace, relationship | Mention is not fitment. Fitment requires explicit configuration IDs; supersession requires its printed target. |
| Procedure step | Sequence, instruction, tool and next-step IDs | Missing prerequisites or unresolved continuation makes it incomplete. |
| Diagnostic node | Entry/test/decision/outcome, operation, expected results and required branch labels | A complete decision needs alternatives; a test needs readings; an outcome has no hidden outgoing edges. |
| Diagnostic edge | Source/target node, label, condition | A lost/duplicate required branch fails complete-node validation. |
| Tool | Name, required operation, optional printed identifier | Do not turn an illustrative drawing label into a verified part identity. |
| Warning | Warning/caution/note and original instruction | Preserve the exact governing scope, not a universal instruction inferred from a nearby note. |
| Region | Table/figure and original caption | An illustrative test example is not a universal specification. |
| Relationship | Prerequisite/next step/diagram/specification/cross-reference target and condition | Required context must resolve and cover every declared vehicle configuration. |

`complete`, `incomplete`, and `ambiguous` are explicit states. The latter two
require a nonempty missing-context list. Schema-valid is not source-correct:
callers must first validate the immutable package/evidence against its manifest,
then call `validate_records` with source text and perform original visual review.
The validator cannot authenticate a reviewer, understand a drawing, or prove
that a human's checked boxes reflect a correct interpretation.

## Separate quality log

`structured-quality-review/v1` uses `structured-quality-policy/v1`. Its append-only
events have `propose`, `approve`, `reject`, or `revoke` actions; approvals/rejections
follow a current proposal, and revocation follows approval. Record hash, intended
use, purpose and full transitive dependency bindings cannot change within a
transition. Events cannot move backward in time. `save_quality_overlay` prevents
editing/truncating existing history and atomically replaces only the named log.
The review tool should serialize writes; cross-process locking is not provided.

Uses are `readable_reference`, `structured_reference`, and
`diagnostic_instruction`. Purposes are `engineering` and `production`.
An agent may create explicitly labeled engineering acceptance, but cannot grant
production approval. Production approval requires a human reviewer. Reviewer
identity is declared metadata, not cryptographic authentication; a future public
review workflow must establish the identity/authority before persisting events.

Checks explicitly record original comparison, values/units, qualifiers,
complete context, complete branches, and source resolution. Reference-only
approval requires original comparison and a resolving source, and may retain
visible incompleteness. Structured-reference/instruction approvals require all
checks and complete dependency context. No approval is inherited from an older
vehicle-applicability event.

Keep reviewed record snapshots. Changing a value, qualifier, source revision,
warning, tool, next step, region relationship or diagnostic branch changes a
bound record/dependency hash. Its existing approval becomes stale or a new
identity becomes unreviewed; both withhold instruction admission. Revocation
also withholds admission without removing history.

## Shared reader / future packet behavior

Two dimensions must remain visible, with their reasons and source links:

| Vehicle applicability | Quality for requested use | Outcome |
| --- | --- | --- |
| Confirmed | Unreviewed/stale/revoked | Reading may be available; no diagnostic instruction. |
| Possible | Approved | Clearly labeled possible reference only; never a vehicle diagnosis packet. |
| Excluded/unmapped | Any | No selected-vehicle search or packet; separate unfiltered original browsing only. |
| Confirmed | Current, complete diagnostic approval | Admit only the same record, configuration, intended use and review purpose. |

The current Phase A reader already shows applicability and withholds diagnostic
readiness. B1 defines the second dimension; bounded B2 displays typed values and
both review dimensions beside originals and persists separate engineering
quality decisions with signed preview/commit. See [B2 acceptance](B2_PROGRESS.md).
B3–B4 complete procedure/graph context and shared packet consumption. These
typed records are not yet in web/CLI AI packets. B4 must use the same eligibility
IDs and both review states in both
interfaces; it need not reproduce their UI layouts.

`diagnostic_admission` takes a caller-validated, configuration-bound scope
decision, not a raw unbound matcher result. Its default purpose is production;
engineering tests must opt in explicitly. The future packet must carry the
record/citation, applicable configuration and scope fingerprint, applicability
trace/events, intended-use quality decision, current record/dependency hashes,
completeness and missing context. Resolve scope **before** loading/searching
text and before constructing packets. Quality cannot bypass an excluded vehicle.

## B1 benchmark and B2/B3 pass criteria

Manual quotations, golden values and page renderings stay outside Git. The local
hand-reviewed benchmark has 16 records covering all nine types and 25 scenarios,
including eight held-out cases. Original page layout review precedes field entry;
`acceptance/b1_verify.py` binds/checks these entries, not extracts them. Authored
regression fixtures cover positive shapes, missing payloads, ambiguous context,
both approval gates, source mutation, wrong vehicles, and stale/revoked history.

For B2/B3, compare actual extracted fields against these frozen golden records:
100% of evaluated safety-relevant values, units, conditions, identity fields,
warnings and branch targets must be correct; no invented value or automatic
promotion is acceptable. Every evaluated record must resolve its original.
Uncertain/unreadable fields must abstain rather than be silently repaired. Missing
qualifiers and wrong-brand/engine cases must load zero forbidden text. A complete
diagnostic branch includes its decision/test, both alternatives, targets, required
readings/tools/warnings/prerequisites and reviewed continuation; otherwise retain
the original as reference and abstain from actionable diagnosis.

The literal-search baseline misses two V10 natural-language queries whose source
answers exist. These remain frozen future retrieval targets, not extraction
failures or evidence that semantic search already works. No query expansion was
added to pass them. Source-reviewed golden records are engineering evidence, not
independent human/mechanic signoff or a claim of complete vehicle coverage.
