# Vehicle and applicability sidecars v1 (A2)

Status: frozen contract and semantic validators. This step defines the data
boundary and expected decisions; the matcher, Ford adapter, imports and search
indexes belong to later A steps. Existing `service-manual-manifest/v1` and
`service-manual-content/v1` records and IDs are unchanged.

## Records and validation

| Record | Contract and schema | Meaning |
| --- | --- | --- |
| Vehicle vocabulary | `vehicle-vocabulary/v1`; `schemas/vehicle-vocabulary-v1.schema.json` | Canonical makes, models, engines, valid model-year/engine tuples and evidence-backed scoped aliases. |
| Applicability evidence | `applicability-evidence/v1`; `schemas/applicability-evidence-v1.schema.json` | Source assertions and optional section/table/figure/region units bound to one normalized package generation. |
| Review overlay | `applicability-review/v1`; `schemas/applicability-review-v1.schema.json` | Append-only scoped proposal/decision events, each bound to exact evidence and interpretation versions. |
| Library references | `service-manual-library/v1`; `schemas/service-manual-library-v1.schema.json` | Multiple package occurrences with distinct roots, hashes and active/superseded state. |
| Scope result | `vehicle-scope/v1`; `schemas/vehicle-scope-v1.schema.json` | Selected filters, mode, version fingerprint and IDs eligible **before** text search. |

`sme.applicability_contracts` provides the corresponding Python validators,
deterministic ID/hash helpers and fixed UI labels/reason codes. JSON Schemas
check portable shape; the Python validators also check references, hashes,
cycles, ranges and transitions. Both are intended to be run by producers and
consumers. Schema validation alone cannot prove that a page's words are true or
that an OCR engine qualifier was read correctly.

All new IDs use SHA-256 over UTF-8 fields joined with NUL, starting with
`vehicle-applicability-v1` and a kind. Prefixes are `make_`, `model_`,
`engine_`, `cfg_`, `unit_`, `ev_`, `review_` and `occ_`, followed by the first
32 lowercase hex characters. The `cfg_` ID includes make, model, model year,
engine and exact qualifier values. A `unit_` ID includes the immutable package
generation hash, parent document ID, kind and selector. Source, publication,
document and asset IDs stay on their original manifest-v1 algorithm.

`revision` and `digest` fields are SHA-256 of canonical JSON: sorted keys,
UTF-8, compact separators and no ASCII escaping. The record's own `revision`
and an assertion's own `id`/`digest` are omitted from their respective hash
inputs. Package `manifest_sha256` uses this canonical manifest hash;
`content_sha256` identifies the content file bytes. The generation hash is
the canonical hash of `[manifest_sha256, content_sha256]`. A producer must
hash-check original files before declaring a package verified. The A6 library
builder will resolve the relative package roots and confirm actual file bytes.

## Identity and evidence rules

A publisher and a vehicle make are separate. Chevrolet and GMC have separate
make IDs; a Ford-published book can name a Lincoln or Mercury vehicle. Engine
identity includes an immutable manufacturer/key, while fuel, displacement and
code are recorded attributes. Equal displacement does not merge Ford diesel
and GM gasoline. Aliases keep their literal spelling, source citation, make
and optional year scope. Overlapping aliases cannot silently point to two
different targets in the same scope.

Each known configuration is one correlated make/model/year/engine tuple.
Evidence alternatives are also individual tuple predicates, never separate
lists of years, models and engines. A validator rejects an exact tuple absent
from the vocabulary. An empty dimension has to say `unknown` explicitly:

| Predicate state | Meaning for matching |
| --- | --- |
| `exact` / year `range` | Source names one canonical value or bounded model-year range. |
| `unknown` | Source does not establish this dimension; it is never a wildcard. |
| `all_in_scope` | Source explicitly covers every value of this dimension within the other bounded fields. For engines, make, model and year must be bounded. |
| `not_applicable` | This dimension does not restrict the stated subject, for example a general chassis item. It does not certify any unrelated model or year. |

Qualifiers can restrict transmission, drivetrain, VIN, RPO, production date,
market, cab, chassis and fuel. A required qualifier missing from a selected
vehicle yields a possible match with `missing_qualifier`, never an invented
value. Year means model year; copyright or file creation dates are not model
years. A fully selected tuple not present in the vocabulary has empty
eligibility and may be shown as missing coverage. Later steps may extend the
vocabulary from reviewed evidence, without silently choosing a nearby engine.

An assertion names its original statement, citation, source unit, include or
exclude intent, correlated alternatives, whether it governs descendants,
derivation and text provenance. Automatic `source_supported` status requires
an explicit structured or bounded textual statement from native source text.
Titles, filenames and heuristics remain proposals. OCR qualifiers remain
proposals until a reviewer checks the original page. A publisher/folder title
is not a vehicle assertion by itself. Source completeness, readability and
vehicle applicability remain separate states.

A child restriction intersects inherited publication/section restrictions.
An explicit child exclusion or contradiction defeats a broad parent include.
Ambiguous scope stays unresolved; a confidence number or accepted parent
label cannot cure it. The matcher in A5 will implement these rules and return
the precise reason codes. A reviewed correction may supersede a mistaken
source assertion, while both the original and decision history remain visible.

The unit sidecar may identify a table, figure, section or PDF region. Every
unit resolves to a v1 document and original citation. PDF pages remain the
default unit. A mixed-engine page can use an `isolated` text projection with
its own hash, or `metadata_only`; `whole` text is rejected for a unit marked
mixed. If isolation is not reliable, engine-filtered text search omits that
unit while the original page remains available by manual navigation.

## Review history and shared content

Review events record proposal, accept, reject, revoke or supersede actions.
Each event includes reviewer, timezone-qualified time, reason, exact target
configuration IDs, relation type, source ID, evidence revision, vocabulary
revision, policy version and evidence ID/digest bindings. A decision must point
to an earlier scoped proposal or acceptance; it cannot broaden target scope.
Old evidence snapshots stay available for validating historical events. An
event is stale when any of its bound evidence, vocabulary or policy revisions
differs from the overlay's current snapshot. Old events remain in the log but
do not grant current search eligibility. A5 will implement persistence and
effective decision reduction.

The relation types distinguish a section that applies, a part that fits, a
part merely mentioned, duplicate content, and the same edition. Only an
accepted, current `section_applies` decision can extend a section's vehicle
eligibility. A shared part number, image or text creates at most a proposal;
it does not approve a procedure. A cross-make proposal stays in review until
an exact section/configuration decision is accepted with citations.

## Search scope and compatibility

The fixed mode labels are **Confirmed matches** and **Include possible
matches**. **Include reference material** is a separate opt-in toggle. A
partially selected make/model/year is browsing a group, not a confirmed exact
vehicle. A deliberate browse-all option is distinct from an empty selection.
An empty non-browse selection has no eligible text. Unknown-make items stay in
an unmapped area and cannot enter a Ford-only scope. Generic references can be
included only with the reference toggle and remain labeled as references.

A scope fingerprint covers library, vocabulary, review and policy revisions,
the selected fields, mode, reference toggle and browse-all state. It changes
when eligibility can change. Search results, snippets, ranking statistics and
limits must be computed from the eligible unit IDs only. A6 exports these IDs;
A7 and A9 enforce the boundary in the app and viewer. Failed index rebuilding
may retain old readable content, but cannot restore eligibility revoked under
a newer review or policy revision.

Old blank make, engine, transmission and drivetrain fields migrate to
`unknown`, not `all_in_scope`. A v1 package without an applicability sidecar
remains readable in manual navigation and visible as unmapped; it does not
become approved vehicle-specific search evidence. Historical citations and
manual IDs remain valid. Synthetic decision cases and expected reason codes
are frozen in `tests/fixtures/applicability_decisions_v1.json`; A5 and later
consumers must execute those outcomes against their implementations.

## A2 verification boundary

The tests cover positive sidecars, unchanged v1 manifest validation, dangling
IDs, wrong-make tuples, overlapping aliases, unbounded engine-all claims,
accidental independent dimension arrays, mixed-page text projections, OCR
promotion, unbound approvals, historical staleness, invalid package references
and empty or stale search scopes. `jsonschema` checks are optional locally and
run when that dependency is installed. These contracts do not import or map
the real manuals; A3 starts the Ford bridge and A4 produces source evidence.
