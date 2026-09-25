# One manual library, organized by vehicle

Status: design only; implementation has not started.
Date: 2026-09-25.
Planning branch: `codex/vehicle-manual-library-plan`, based on merged
extractor `main` at `9341637306af6595ab4233b39db7f80693d7069b`.
Repair Buddy baseline: merged `main` at
`310ce810f9129576d5f0f72b37a27f35cac699a8`.

This is a new sequence, numbered **A1–A10** and **B1–B4**, separate from the
completed GM integration Steps 0–8. Execute one selected step per task. This
document does not implement code, migrate a database, or process more manuals.

## 1. Decisions agreed with the owner

- Own this plan and the common extraction/mapping contracts in
  `service-manual-extractor`.
- Cover the whole experience: input discovery, extraction, vehicle mapping,
  review, search, Repair Buddy, and the standalone offline viewer.
- Organize by **make, model, model year, and engine**. Preserve additional
  qualifiers when the manual requires them.
- Treat similarity and shared-part relationships as **possible matches
  requiring review**, not automatic procedure applicability.
- Deliver searchable pages, diagrams, tables, citations, and vehicle mapping
  first. Deliver structured procedures, specifications, part records, and
  diagnostic steps afterward.
- Prepare the evidence for later AI integration. The first delivery needs no
  model API key or AI calls. Codex model recommendations below concern doing
  development work, not models embedded in the finished application.

The user has obtained replacement GM HTML files. Do not repeat recovery work
on the earlier USB copies or make that damage a project blocker. Record and
validate the replacement input during A1/A4 when it is available locally.
Previous extraction reports describe the earlier inputs, not the replacements.

## 2. What exists today

These are different inventories and processing stages; their counts must not
be added together as though all of them were imported into one live library.

| Material | Current evidence | Implication for this plan |
| --- | --- | --- |
| Ford service-disc collection | Four preserved source folders; 64 catalog entries and 44 unique archive hashes. The 41 extracted English publications are 33 indexed and 8 indexed-partial; 23 entries remain cataloged. The live database has 18,292 documents, 64,906 fragments and 484 applicability rows. | Reconcile source occurrences, duplicate editions, partial reasons, extracted publications and indexed books individually; preserve current citations. |
| Vehicle labels in those discs | Catalog models include Ford, Lincoln and Mercury names. The 484 applicability rows have empty make, engine, transmission and drivetrain fields. | A Ford-produced disc is not proof that every publication is for a Ford-branded vehicle. Missing engine metadata is not all-engine coverage. |
| Standalone Ford owner PDF | `2003-f-super-duty-owner-guide.pdf`: 280 native-text pages in the older PDF/manual tables. | Bring the older PDF path under the same scope rules; retain its owner-information role and old links. |
| Reviewed GM seller PDFs | 113 publications, 12,324 pages: 7,606 native-text pages and 4,718 OCR-derived pages. All are present in the normalized package and offline viewer. | These provide a substantial PDF acceptance set. They are system articles and assorted manuals, not proven complete coverage for every seller-labeled year/model. |
| GM application acceptance | Three GM publications, totaling 107 documents/fragments, were indexed into a disposable database copied from the Ford database. The other 110 were cataloged there. | The live Repair Buddy database is not already a fully imported Ford+GM library. Migration/import is an explicit step below. |
| GM HTML | Existing adapter and authored examples retain HTML structure, navigation, diagrams and applicability statements. Replacement originals are owner-reported. | Use the replacement identity for new acceptance; do not transfer verification from an older or different input. |

Local records to reconcile in A1:

- Ford and standalone PDF: `/Users/asokmathews/Documents/repair-buddy/data/`,
  including `repair-buddy.sqlite3` and `manuals/2003-f-super-duty-owner-guide.pdf`;
  consult that repository's `docs/ford-media-inventory.md`,
  `docs/ford-manual-audit.md`, and `docs/ford-super-duty-coverage-audit.md`.
- GM originals/reports:
  `/Users/asokmathews/Documents/service-manual-data/gm-seller-download-2026-09-17`.
- Reviewed GM package:
  `/Users/asokmathews/Documents/service-manual-data/step6-acceptance-2026-09-23/normalized-ad550c5`.
- GM acceptance database:
  `/Users/asokmathews/Documents/service-manual-data/step6-acceptance-2026-09-23/repair-buddy-final.sqlite3`.
- GM offline viewer:
  `/Users/asokmathews/Documents/service-manual-data/step7-viewer-final-2026-09-25`.

Counts above come from existing reports and read-only database/manifest checks,
not a new full extraction or a new validation of every original file.

### Reuse the working foundations

The extractor already preserves source hashes, exact publication selections,
safe HTML structure, original PDF/page citations, native/OCR provenance,
references, diagrams and captions. Repair Buddy already provides cataloging,
transactional ingestion, full-text search, vehicle profiles and linked readers.
The toolkit supplies PDF text/OCR utilities; ordinary HTML should continue to
be parsed directly, not converted to a scanned PDF and OCRed.

There are specific gaps to close:

1. `fsd` reads Ford discs, but the live Ford output has not been connected to
   the neutral `sme` document package. Declaring Ford in the contract and testing
   synthetic Ford records did not implement that bridge.
2. One neutral package supports many publications but only one source. The
   viewer does not yet assemble several Ford/PDF/HTML packages into one library.
3. Current HTML detection targets the `index.html` + `pages/` export layout.
   Arbitrary HTML exports and mixed outer folders need explicit discovery and
   format handlers; the current reader must not be described as universal.
4. Applicability is partly structured book metadata and partly free-text
   statements. Canonical vehicle/engine IDs, persistent human review, and
   shared-content applicability are missing.
5. Repair Buddy can accept structured parent coverage without considering a
   conflicting child page/caption. Other paths replace parent statements with
   child statements. Neither behavior correctly preserves all constraints.
6. The app scopes its primary search by book but still searches conflicting
   books for exclusion examples and queries the older PDF table separately.
   Page-level checks happen after the result limit. The viewer ranks its whole
   index before filtering to the chosen manual.

These findings require changes to the retrieval boundary, not just new UI
selectors. Primary code/document references are listed at the end of this plan.

## 3. Architecture and responsibility

The desired flow is:

```text
Owned discs / PDFs / HTML folders / supported archives
    → discover and verify sources
    → format adapters (Ford archive / static HTML / PDF)
    → immutable normalized packages and original citations
    → versioned vehicle vocabulary + source applicability evidence
    → review decisions and shared-content relationships
    → effective eligible content for a selected vehicle/scope
    → search only that content
    → Repair Buddy, offline viewer, later bounded AI evidence
```

| Owner | Responsibilities |
| --- | --- |
| `service-manual-extractor` | Format discovery/adapters; immutable normalized packages; portable vehicle/applicability contracts; deterministic reference matcher; multi-package library manifest; review-overlay validation; static viewer generation. |
| `Repair Buddy` | Saved vehicles and cases; application database and migrations; review queue and decision persistence; search scope/cache; filter controls; readers; future evidence tools. It consumes the shared matcher and contracts. |
| `workshop-manual-toolkit` | PDF inspection, native-text extraction and optional OCR derivatives. Keep independently versioned. Add an integration change only if an identified PDF requirement needs it. |

The current Repair Buddy design says it owns applicability. Refine that boundary
explicitly when implementing A7: the app owns decisions and user workflow, while
the extractor owns portable semantics and the reference matcher. Do not maintain
two conflicting sets of Ford/GM matching rules or make the extractor import
Repair Buddy. Keep the dependency direction one-way and pin tested revisions.

### Immutable content plus editable interpretation

Keep the frozen manifest/content v1 contracts valid. Do not insert new fields
into schemas that reject extra properties, and do not redefine historical IDs.
Add separate versioned artifacts referencing the existing source, publication,
document and asset IDs plus hashes. The names below are proposed contracts to
freeze in A2, not commands or formats already implemented:

| Artifact | Minimum purpose |
| --- | --- |
| Vehicle vocabulary | Stable make/model/engine IDs; literal labels; scoped aliases; valid vehicle combinations; optional qualifiers; evidence and vocabulary version. |
| Applicability evidence | Exact source statement/locator; subject unit; include/exclude meaning; correlated configuration alternatives; derivation rule and native/OCR provenance. |
| Review overlay | Persistent proposed/accepted/rejected/revoked/stale decisions; reviewer, time, reason, supporting citations and bound evidence hashes. |
| Library manifest | References to multiple verified packages; hashes and relative roots; active/superseded source occurrences; vocabulary, review and policy versions. |
| Scope/search export | Effective eligible unit IDs, match explanations and scope fingerprint; search partitions with the same eligibility semantics. |
| Structured records (Phase B) | Typed facts/steps/parts/relationships anchored to the originals and governed by the same applicability/review contracts. |

Artifacts and all manual text stay in local data storage outside Git. Commit
schemas, synthetic examples, tests, metadata summaries and code. Changing a
vehicle alias or a review decision should rebuild affected mapping/search
artifacts without rerunning decompression or OCR.

### Vehicle identity must preserve real combinations

- Separate source publisher, vehicle make, model family, exact model and
  display label. Chevrolet and GMC remain separate makes; GM is an
  organization/family label. A Ford disc can contain Lincoln or Mercury.
- Keep literal labels such as `F-Superduty`, `F-Super Duty`, and
  `F-Super Duty 250-550`. Any mapping to canonical models needs evidence and
  retains the source label; a broad family must not silently become every trim.
- Engine displacement alone is insufficient. Retain family/code, fuel,
  displacement, brand/era and qualifiers where known. Ford 6.0L diesel and
  GM 6.0L gasoline must never collapse to one engine.
- Store alternatives as correlated tuples/predicates, for example
  `(2003, F-250, 6.0 diesel) OR (2002, F-250, 7.3 diesel)`. Do not independently
  collect year/model/engine lists and generate their Cartesian product.
- Use model year, not a document copyright date. Preserve production dates,
  VIN breaks, RPO codes, market, cab/chassis, transmission and drivetrain as
  optional restrictions. Surface these when they matter to a match.
- Distinguish **unknown**, **explicitly all variants within a defined scope**,
  **not applicable as a dimension**, and a specific value/range. Empty strings
  from the old catalog migrate to unknown, never to a wildcard.
- Start with an evidence-backed vocabulary for the manuals in hand and a
  synthetic unrelated make/car example. Do not require a purchased universal
  vehicle catalog or a remote VIN service for the first delivery.

### Applicability belongs to content, not just books

The logical hierarchy is source → publication → section → document/page →
table/figure/region. Reuse existing nodes and introduce sidecar unit identifiers
for stable section/block/row/figure selectors where needed. Every selector must
resolve to an original citation and a specific extraction generation.

Book labels define context; they do not approve every engine row inside a book.
Evaluate inherited and local constraints together. A child may narrow context
or exclude a variant. A contradiction must remain visible and cannot be cured
by a high confidence score or an accepted parent label. A reviewed correction
can supersede an erroneous assertion, with its evidence and history retained.
If an assertion's scope is ambiguous, keep it unresolved instead of guessing
which sibling pages or rows it governs.

Bounded, tested parsing of an explicit source applicability statement can yield
a source-supported mapping automatically. General title/filename matching,
first-page PDF text, incidental engine mentions and heuristic label extraction
yield proposals. An OCR-derived qualifier needs review against the page before
it can create a confirmed mapping in the first delivery. Completeness of the
source, quality of the text and vehicle applicability are separate attributes.

In Phase A, HTML can retain explicit table/figure selectors already present in
its structure. PDF units remain pages unless an original/reviewed locator
establishes a narrower region. A subpage search projection must contain only
that eligible unit's text plus the required headers/context, not the containing
document's full text. If text from a known mixed-engine page cannot be isolated
reliably, omit it from engine-filtered text search in both matching modes.
Keep the original discoverable through metadata/manual navigation with a
mixed-content explanation. It may participate in a broader scope only when
that scope actually allows all its searchable content. Readability is separate
from approval as an engine specification or an actionable diagnostic unit.

### Shared parts and shared sections

Represent these as different relationships:

- a page **mentions** a part number;
- evidence says a part **fits** a particular configuration;
- a cited section/procedure **applies** to a particular configuration;
- two files contain identical bytes/text or two occurrences represent the
  same publication edition.

None of these relationships automatically implies the next. Same text or the
same apparent part number can suggest a review item. Part numbers need a
manufacturer/catalog namespace and qualifiers; a supersession needs its own
evidence. Shared hardware does not prove identical wiring, calibration, torque,
access procedure or diagnostic branches. Do not infer transitive applicability
through chains of shared components.

The existing Ford edition audit found reused diagrams and similar wording
across adjacent years without establishing exact interchangeable procedures
or specifications. Preserve editions and their qualifiers even when grouping
duplicate-looking search results. GM article headers can explicitly name
several Chevrolet/GMC/Cadillac models; retain those paired claims rather than
inheriting the seller folder's broad year range.

A reviewed section can link to several vehicle configurations without copying
its content. Approve a precise subject and target configuration with supporting
citations; never approve an entire book because one component is shared. Pending
cross-make suggestions live in the review queue. They do not cause GM text to
enter a Ford search. An explicitly reviewed Ford applicability link may later
make that particular cross-published section eligible, with its original source
clearly labeled.

### Review and lifecycle

Keep source evidence, review state and query result distinct. A review item
stores the proposed subject/vehicle relationship, exact evidence, derivation,
decision, reason, reviewer identity/time and hashes. An approval may apply to
several configurations only if the selected scope is explicit. Reject, revoke,
and supersede must be supported; do not delete the old decision history.

Reimporting unchanged evidence retains the decision. A changed source hash,
selector, normalized evidence, parser interpretation or policy/vocabulary
version triggers a dependency check; affected approvals become stale until
revalidated. Unaffected decisions should survive. Matching and search caches
include these versions and cannot serve a formerly approved result after
revocation. Repackaged identical content may be linked as equivalent, but new
source occurrence IDs and citations remain intact and reviews are not silently
copied to an unverified replacement.

## 4. Search and reader behavior

### Filters and matching modes

Provide make → model → year → engine selectors in that order, with values and
counts derived from actual cataloged evidence. A saved vehicle fills them in.
Changing an earlier selector clears incompatible later selections. Offer a
clear reset and a deliberate browse-all-library mode. An engine absent from
the library is shown as missing/unknown coverage, not silently substituted.

Use the same three matching choices in the app and viewer:

| Mode | Eligible material |
| --- | --- |
| Confirmed matches (default for a fully selected vehicle) | Explicit source-supported or reviewed mappings that satisfy the selected configuration and required qualifiers. |
| Include possible matches | Adds compatible but incomplete evidence within the chosen scope, with the missing fields/reason shown. Known contradictions remain excluded. Pending cross-make similarity proposals remain in the review queue. |
| Reference material | An explicit opt-in for generic/background material, clearly separated from vehicle-specific repair coverage. This can be combined with a chosen vehicle scope. |

The third choice may be presented as a checkbox beside the first two modes so
generic reference material does not replace the vehicle query. Freeze that UI
wording in A2 and use it consistently. A partial filter such as only `Ford`
means browsing a vehicle group, not confirmation for an exact vehicle. A saved
vehicle missing a restriction required by a page gets a possible-match result,
not an invented transmission/engine selection. Unknown-make content does not
enter a Ford-only search; it remains available in the unclassified review area.

### Apply the scope before text search

First resolve eligible source/publication/document/unit IDs using metadata,
selected filters, mode, explicit exclusions and current review decisions. An
empty scope returns an empty result and a coverage explanation. Then tokenize,
retrieve, rank, form snippets and count results using only that eligible text.
Apply limits last. Do not perform a second text query over excluded manuals
just to explain exclusions; metadata can provide reasons/counts.

Initial implementation design:

- Repair Buddy uses an on-demand, bounded cache of search projections containing
  only eligible units. Reuse SQLite FTS5 and the existing retrieval interfaces.
  Build the projection from an explicit ID allowlist, then query it. A shared
  global FTS query with a later SQL/UI filter is not sufficient evidence that
  excluded text was not searched. Do not prebuild an index for every possible
  vehicle combination.
- The viewer build produces a small metadata manifest and text/index shards
  grouped by effective applicability. Resolve scope before fetching any search
  shard; split a heterogeneous shard if it would load excluded text. Compute
  ranking statistics from the active eligible content. Querying a Ford scope
  must never fetch a GM-only text/index shard.
- Keep the reference matcher authoritative in Python. Export evaluated scope
  memberships/decision data for the viewer's known configurations so the UI
  selects/intersects memberships rather than inventing new regex rules.
  Unknown configurations fail clearly; adding a new reviewed mapping requires
  rebuilding the export. Freeze the supported partial-filter, mode and unknown
  required-qualifier states in A2 and export decisions for those states too.
  Simply unioning fully specified vehicle memberships is insufficient: an
  unknown RPO or transmission may change confirmed eligibility. Validate these
  cases with the same decision vectors as the application.
- Cache keys include library generation, vehicle scope, mode, vocabulary,
  policy and review revision. Keep disk/memory usage bounded, cancel obsolete
  searches, and prevent an older async result from appearing after a filter
  change. All fallback search paths obey the same allowlist.

It is acceptable to inspect the small library metadata catalog to choose a
scope. The promise is that excluded manual text is not retrieved, token-matched,
ranked, excerpted or supplied as evidence for that query. Tests must observe
which search partitions and unit IDs were visited, not only which rows appeared.

### Reading, navigation, and review

Show title, source/manual role, year/engine scope, match status, unknown
qualifiers, and native/OCR provenance alongside every result. Open the original
PDF at the exact page or the safe HTML at its source anchor. Keep diagrams,
captions, surrounding context and tables; do not flatten away their conditions.

Return links restore filters, mode, query and result position. A source link
leading outside the current vehicle scope explains that mismatch before
opening as reference material; it does not silently broaden search scope.
Opening surrounding context is distinct from approving that context as evidence.

Repair Buddy owns the review UI: inspect the original and proposal together,
choose a specific configuration/content scope, accept/reject with a reason,
and preview what becomes eligible. The standalone viewer initially consumes a
read-only reviewed snapshot and displays pending/stale labels. It links to the
local review workflow or explains how to rebuild the snapshot; it must not
pretend that a static file can persist a shared review decision. Label approvals
"as of review revision/date". A disconnected viewer cannot discover a later
revocation. Current approval status requires replacing/rebuilding its local
snapshot; app/viewer parity comparisons always use the same revisions.

If rebuilding content fails, retain the previous successful content generation.
It remains searchable only while its review, policy and scope dependencies are
still valid. A revoked approval cannot become searchable again because a new
index build failed. Keep originals readable and block/rebuild the affected
stale search projection instead of falling back to outdated eligibility.

## 5. Sequential implementation plan

All steps below are **not started**. Each task must report changed files,
tests/evidence, remaining issues, and the next step with its model recommendation.
Stop at that step's pass gate. A pass gate is not permission to merge or release.

### Model guidance for this plan

Recommendations are workload judgments, not measured rankings on this project
or promises about Codex credit usage. Official guidance describes Sol as suited
to coding and judgment, Luna as efficient for scoped work, and Astra for harder
analysis. It recommends testing the lightest setting that meets the quality
bar: [OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection).
Sol supports High reasoning:
[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol).

Use the exact model/effort listed as a starting point if available in your
selector. These are dated recommendations and should be rechecked if model
names/settings change. Do not raise every step to Ultra by default. A focused
retry on an unresolved contract or matching issue can use Astra High; routine
inventory and rendering work should not require it.

| Step | Deliverable | Repository | Recommended model / reasoning |
| --- | --- | --- | --- |
| A1 | Reconciled inventory and reviewed acceptance examples | Extractor docs + local reports | GPT-6 Luna / Medium |
| A2 | Vehicle, applicability and review contracts; truth tables | Extractor | GPT-6 Sol / High |
| A3 | Ford-to-neutral adapter with legacy identity bridge | Extractor | GPT-6 Sol / High |
| A4 | Consistent HTML/PDF/Ford evidence capture and input orchestration | Extractor; toolkit only if needed | GPT-6 Sol / High |
| A5 | Shared matcher, scoped shared-content proposals and review overlays | Extractor | GPT-6 Sol / High |
| A6 | Multi-package library, eligibility exports and scoped search indexes | Extractor | GPT-6 Sol / High |
| A7 | Repair Buddy migration and single scoped retrieval path | Repair Buddy | GPT-6 Sol / High |
| A8 | Repair Buddy filters and persistent review workflow | Repair Buddy | GPT-6 Sol / High |
| A9 | Offline viewer filters and matching parity | Extractor | GPT-6 Sol / High |
| A10 | Real-library migration acceptance and first-delivery checkpoint | Both repos | GPT-6 Sol / High |
| B1 | Structured-record contract and independently reviewed examples | Extractor | GPT-6 Sol / High |
| B2 | Typed specifications and part-reference extraction | Extractor; Repair Buddy reader | GPT-6 Sol / High |
| B3 | Procedures, diagnostic branches and context-preserving units | Extractor; Repair Buddy reader | GPT-6 Astra / High |
| B4 | Shared bounded evidence retrieval and final evaluation | Both repos | GPT-6 Sol / High |

### A1 — Reconcile what is available and choose acceptance examples

**Depends on:** this plan. **Model:** GPT-6 Luna / Medium, because this is a
bounded inventory of existing records rather than architecture work.

Read the current handoffs and inspect source manifests, local paths, inventory
reports and read-only database summaries. Produce one local inventory recording
original identity/hash, source occurrence, publication/edition, adapter,
extraction/normalization/indexing stage, native/OCR counts, current vehicle
evidence and the next required action. Include all Ford brands, the legacy
owner PDF, all 113 GM PDFs, and the replacement HTML path when supplied/found.
Include unsupported/unindexed inputs rather than silently omitting them.

Do not repeat successful OCR or re-extract everything just to count it. Mark
old copies as superseded only with recorded replacement evidence. Separate
unknown coverage from missing or unreadable content. If the replacement path
cannot be located, record that specific pending path and proceed with the other
inputs; do not restart USB recovery.

Create a small manually reviewed acceptance set with positive and negative
examples: Ford 6.0 diesel vs another Ford engine, Lincoln/Mercury brand identity,
GM 6.0 gasoline vs 6.6 diesel, multiple models sharing an explicitly applicable
section, a contradictory table/figure, a mixed-engine PDF page, generic DTC
reference, owner material, and an unknown/misleading label. Use authored analogs
in Git and keep exact real citations/answers in local reports. Capture current
search timings and the machine/software versions for later comparison.
Choose real positive cases only where the source supports them; use synthetic
cases for an otherwise unavailable variant rather than manufacturing coverage.

**Pass:** every discovered input has a named processing state; counts reconcile
without treating duplicates or catalog-only items as imports; enough reviewed
examples exist to test each decision above. Commit the metadata summary only.

### A2 — Freeze the vehicle and applicability contracts

**Depends on:** A1. **Model:** GPT-6 Sol / High, because identity and scope errors
would affect every later layer.

Specify and implement separately versioned schemas/validators for the vehicle
vocabulary, evidence, review overlay, library references and scope results.
Retain source statements and locators as the authority. Define stable IDs for
new sidecar units without altering v1 IDs. Define canonical aliases and valid
tuples, include/exclude scope, explicit-all vs unknown, inheritance, mixed pages,
auto source-supported criteria, review staleness and policy versioning.

Freeze a language-independent set of decision examples and expected reason
codes for exact matches, incomplete filters, conflicts, generic references,
unknown identity, reviewed shared sections and stale decisions. Fix the mode
wording, reference toggle and the treatment of unselected required qualifiers.
Define migration rules for old blank fields and compatibility with packages
that have no applicability sidecar. Such packages remain readable and visible
as unmapped material, not automatically approved search evidence.

**Pass:** schemas and semantic validators reject dangling IDs, invalid ranges,
unbound approvals and accidental cross-products; every hard matching case has
an agreed expected result; existing v1 fixtures still validate unchanged.

### A3 — Connect Ford extraction to the neutral package

**Depends on:** A2. **Model:** GPT-6 Sol / High, because the bridge must preserve
working Ford behavior and historical identities across formats.

Wrap the existing Ford archive discovery/extraction/parser modules behind a
neutral adapter. Retain exact source-relative archive selection and every
selected book, including multiple books with the same role or display code.
Produce the neutral content/assets/navigation/citation package and a mapping
between old Repair Buddy/Ford identifiers and the new source occurrence IDs.
Reuse tested parsing already in the repositories through a clear dependency
boundary; do not make the extractor depend on Repair Buddy.

Handle supported Ford archive generations and observed workshop, wiring and
diagnostic formats explicitly. Keep original PDF/SVG/raster assets and source
anchors. Unsupported MDB/XML/other content gets a precise capability report,
not invented converted content. Existing `fsd` commands continue to work;
non-Ford HTML/PDF readers never call the Ford EPL parser.

**Pass:** Ford synthetic v1/v2 and selected real books produce neutral packages;
two workshop publications coexist; old citations resolve through the identity
bridge; content/asset checks and the existing Ford regression suite pass.

### A4 — Capture applicability evidence consistently across inputs

**Depends on:** A3. **Model:** GPT-6 Sol / High, because scope and evidence
quality differ substantially between HTML, disc metadata and PDF pages.

Add format discovery/orchestration that inventories a mixed outer folder and
routes each recognized source to its adapter. Make adapter capabilities
explicit. Add support for another static HTML layout only with detection,
authored fixtures and a known source example; list unsupported inputs clearly.

Emit source evidence from structured catalog fields, titles, breadcrumbs,
section headings, exclusions, table/figure qualifiers and PDF page locators.
Preserve the original words, context, confidence basis, selector, include/exclude
intent and relevant engine/variant qualifiers. First-page PDF evidence does
not automatically apply to the whole publication. A publisher or folder title
is not automatically a make/model assertion.

Reuse native PDF/HTML text. Invoke toolkit OCR only for pages needing it,
recording source/derived hashes, tool version, page correspondence and warnings.
The current toolkit detects pages with no text; a scanned diagram with a
native footer may escape that test. Flag low-text/mixed pages for inspection
and selective OCR rather than treating any native text as proof of readability.
Bind corrected OCR or qualifier review to the exact original page. Validate
the replacement HTML as its own input when its path is available. Cache by
source and transformation identity so unchanged successful work is reused.

**Pass:** all three format families yield the same evidence contract; misleading
dates/titles, OCR qualifier errors and mixed sections remain distinguishable;
originals and their citations remain intact; unsupported items are counted.

### A5 — Implement matching, shared-content proposals and review storage

**Depends on:** A4. **Model:** GPT-6 Sol / High, because exclusion precedence,
review lifecycle and many-to-many applicability need careful testing.

Build a pure, deterministic matcher over canonical scope + source evidence +
review overlay. Implement the A2 truth tables. Intersect inherited restrictions
and evaluate units before scoring. Return effective state, supporting evidence,
conflicts and missing qualifiers; a numerical similarity score cannot override
a contradiction. Store review events separately from generated catalog rows so
recataloging cannot erase them.

Generate bounded review proposals from explicit source cross-references,
matching contextual identifiers and duplicate content. Record the basis and
target scope. This initial proposal mechanism does not require full Phase B
part extraction or a cloud model. Approve only the specified relationship;
shared part, duplicate file and shared procedure remain separate types.

Add validate/import/export support for the portable review overlay. Test
unchanged reimport, changed evidence, rejection, revocation, supersession and
staleness. Display accepted reviews as human decisions with cited support, not
as rewritten source statements.

**Pass:** all truth tables pass; neither similar text nor a shared part creates
an unreviewed confirmed match; child conflicts defeat broad parent approval;
review history survives reimport and affected stale approvals stop matching.

### A6 — Assemble many sources and build eligible search data

**Depends on:** A5. **Model:** GPT-6 Sol / High, because this establishes the
pre-search boundary and handles invalidation across many packages.

Implement a library manifest referencing several normalized packages, a
versioned vocabulary and the selected review revision. Validate every reference
and retain both publication occurrence and any reviewed edition/equivalence
relationship. Never overwrite books by role or duplicate filename. Original
citations remain separate even when search display groups equivalent copies.

Resolve selected scope into eligible unit sets and export match reasons and
filter counts. Generate offline scope memberships and search shards as described
above. Define the common scope fingerprint, cancellation behavior, atomic
publication and bounded cache policy for consumers. A rejected/stale decision
invalidates dependent eligibility and indexes. No-content and unsupported-input
states are visible and cannot silently widen the scope.

**Pass:** a combined fixture holds multiple Ford books, GM PDFs and HTML;
Ford-only requests visit zero GM-only search shards; year/engine restrictions
apply before term matching, statistics, snippets and limits; failure retains
the previous content generation without reviving invalidated eligibility.
Static export and Python membership agree on the A2 test vectors, including
incomplete vehicle/qualifier selections.

### A7 — Migrate Repair Buddy and unify its retrieval path

**Depends on:** A6. **Model:** GPT-6 Sol / High, because this changes persistent
data and must preserve existing cases, citations and search history.

Create a separate Repair Buddy implementation branch from its current merged
main using a clean checkout/worktree. Pin the extractor revision with A6.
Introduce explicit versioned database migrations for vocabulary, evidence,
unit membership, review events and index generations. Back up and migrate a
disposable copy first. Preserve the current database, its legacy PDF records,
Ford IDs/citations and uncommitted project-design edits.

Import all normalized formats through a shared library contract while retaining
old source adapters as compatibility paths. Map the 280-page owner PDF into
the common searchable unit model. Replace hardcoded make/model matching with
the shared matcher. Build/query scope-specific FTS projections or an equivalent
implementation proven to meet the strict pre-search boundary.

Remove implicit conflicting-book searches and the unscoped legacy PDF fallback
from vehicle-selected search. Preserve literal search and case/pilot routes,
but require every route to carry the same explicit scope; missing/empty scope
must not become the entire library. Reimport and failed migrations retain the
last successful content generation and reviewer history, subject to current
eligibility before any fallback search is allowed.

**Pass:** migration/rollback fixtures and old Ford/PDF links pass; known excluded
books/pages are never searched by any fallback; a relevant result beyond the
old first-100 boundary is recovered; source and review provenance is retained.

### A8 — Add the filter controls and review workflow in Repair Buddy

**Depends on:** A7. **Model:** GPT-6 Sol / High, because user decisions, scope
state and asynchronous search must remain consistent across several screens.

Implement cascading make/model/year/engine controls, the agreed matching modes,
saved-vehicle prefill, explicit browse-all reset and optional qualifier prompts.
Show available/unknown coverage from metadata before the user searches. Explain
empty results without performing queries against excluded content.

Build the review queue with original-page access, highlighted evidence,
proposed relationship/target scope and accept/reject/revoke actions. Provide a
preview of affected vehicles/content before saving. Bulk review may operate
only on explicitly selected equivalent scopes with visible evidence; a generic
"approve all similar" operation is not part of this delivery.

Carry filters, matching mode, query and return position through HTML/PDF reading,
diagram views, source links and browser history. Explain source links outside
the active scope. Show stale and possible states accessibly at desktop/phone
width and with keyboard controls. Review changes refresh eligibility and any
open search without changing a saved vehicle's identity.

**Pass:** the same user tasks succeed for all formats; an approval/revocation
changes only its intended scope; filter changes cannot display results from an
old request; reviewers can trace every decision back to an original citation.

### A9 — Give the offline viewer the same vehicle-scoped experience

**Depends on:** A8. **Model:** GPT-6 Sol / High, because the existing viewer
search ranks globally and must change without breaking legacy Ford viewing.

Consume the multi-package library and compiled eligibility exports. Add the
same selectors, mode labels, match explanations and coverage states. Load only
eligible text/index shards, compute scope-local search statistics and enforce
empty-scope behavior. Preserve all independently selectable publications,
nested navigation, diagrams/captions, source links and exact PDF pages.

Persist filter/query/return state in local routes. Show the snapshot's library
and review revision/date and label decisions as of that snapshot. An older
disconnected export cannot detect newer decisions; replacing the export is the
first-delivery update mechanism, and "currently approved" is not a valid label.
Reviews remain read-only here; point to the application workflow for changes.
Maintain the existing legacy Ford viewer path and clearly separate unsupported
filtering on old builds from newly generated neutral libraries.

**Pass:** browser instrumentation with network access disabled shows zero
GM-only shard loads for a Ford scope; the app and viewer return the same eligible
IDs/statuses for the shared fixtures at the same revisions;
desktop/phone/keyboard/return flows pass.
Updating the review overlay and rebuilding changes the expected memberships.

### A10 — Validate the first delivery using the manuals in hand

**Depends on:** A9. **Model:** GPT-6 Sol / High, because this is a cross-repository
acceptance run requiring interpretation of failures, not just command execution.

Run all regression gates from fresh environments with pinned dependencies.
Using the A1 inventory, resume/convert supported packages into a combined local
library and populate a disposable Repair Buddy database. Reuse verified
extractions and OCR. Catalog-only GM publications must either be imported or
have an explicit pending reason. Keep originals and the existing live database
intact until the tested migration is ready; retain a recoverable backup when
promoting the completed library for normal use.

Evaluate the reviewed real examples and the adversarial matrix below through
both UIs. Compare inventory counts and old/new citations, verify page/assets
by their recorded hashes, and sample diagrams/tables/OCR against originals.
Measure cold index-build and warm search performance, memory/disk cache bounds
and cancellation on the recorded machine. Provisional usability targets are
warm filtered searches under one second at p95 and a responsive/cancellable
cold build with visible progress; document measured exceptions before calling
the user-facing release ready.

**Pass:** every supported inventoried item is imported/available or explicitly
pending; no unexplained document loss or wrong-vehicle leakage; reviewed
positive/negative examples pass in both readers; source/derived/review counts
are reproducible; all local checks and relevant CI pass. Publish an engineering
acceptance report and update the handoff with exact revisions and next steps.
Demonstrate useful confirmed search on reviewed Ford and GM configurations,
plus correct possible/reference behavior on native PDF, OCR PDF and HTML.
Pending inventory entries cannot substitute for these working end-to-end cases.
Missing replacement-path information may remain a named input gap rather than
failing the tested first delivery for the other manuals. Do not label a vehicle
fully covered just because its available files are all processed.

**Delivery checkpoint:** the first version is usable here. Stop before Phase B
until the user selects it. No public release or live AI diagnosis is implied.

## 6. Phase B — Expanded extraction after the first delivery

### B1 — Define typed records and reviewed ground truth

**Depends on:** accepted A10. **Model:** GPT-6 Sol / High, because typed records
need precise source anchors and evaluation criteria before extraction scales.

Define schemas for procedure steps, specifications, part references, diagnostic
nodes/branches, tools, warnings/prerequisites and diagram/table regions. Each
record names its original unit/locator, exact source wording, type, units and
conditions where relevant, applicability predicate, extraction version, review
state and source/text hashes. Preserve original and normalized values together;
absence of a value is not zero. Do not conflate part mention, fitment and
supersession. A generic bag of key/value pairs is insufficient.

Choose a small reviewed benchmark across native HTML, Ford tables, native PDFs
and OCR PDFs. Include deliberately unreadable/ambiguous examples with an
expected abstention. Review expected answers from the original page, separate
from the extraction logic; keep a held-out subset to prevent tuning to every
test. Set field-level accuracy/abstention criteria and the definition of a
complete diagnostic branch before selecting an extraction approach.

**Pass:** every proposed type has schema validation, a locator that opens the
source, positive/negative/abstention examples, and explicit quality gates. No
Phase A reader or mapping behavior regresses.

### B2 — Extract specifications and part references

**Depends on:** B1. **Model:** GPT-6 Sol / High, because numbers, units and
conditions must remain attached to their exact row and vehicle context.

Start with structured HTML/Ford tables and clear native PDF text. Add reviewed
PDF regions/layout extraction only where it improves the benchmark. Preserve
row/column headers, merged-cell inheritance, units, ranges, stages, footnotes,
engine conditions and source spelling. Do not silently repair OCR numbers or
convert an uncertain printed part identifier to a catalog identity.

Link extracted parts to candidate shared-content reviews, without auto-approving
procedures. Show typed values with original context in the reader. Any optional
model-assisted extraction remains a proposal requiring provenance and the same
validation; adopting a paid runtime service needs its own explicit product
decision and cost/data plan, not just a Codex model selection.

**Pass:** held-out typed values retain their conditions/citations, ambiguous
values abstain, and mismatched engines/units/part namespaces cannot combine.
Incorrect or unreviewed records cannot be promoted to actionable evidence.

### B3 — Extract procedures and diagnostic structure

**Depends on:** B2. **Model:** GPT-6 Astra / High, because branched diagnostics,
cross-page context and completeness judgments are the most demanding part of
this plan. This is a development recommendation, not an extractor runtime
requirement.

Represent ordered steps and diagnostic graphs with warnings, prerequisites,
tools, measurements, expected values, Yes/No branches, terminal outcomes and
cross-page dependencies. Keep conditional alternatives separate and inherit
applicability at the narrowest supported scope. Preserve source context instead
of inventing a missing branch, connector, expected reading or test instruction.

Use deterministic parsing where structure is explicit. When layout/OCR prevents
reliable graph construction, retain the original as readable reference and
flag the missing structure for review. Reader views should expose the original
table/page beside the interpreted steps so reviewers can find branch errors.

**Pass:** complete reviewed graphs retain every edge/condition on the benchmark;
missing branches and wrong-engine rows cause an incomplete/unapproved result;
source links and original reading remain available regardless of extraction
success. No general diagnostic-readiness claim follows from page indexing.

### B4 — Prepare common evidence tools for later AI and evaluate

**Depends on:** B3. **Model:** GPT-6 Sol / High, because retrieval boundaries,
staleness and structured context must remain consistent through the application.

Extend the local evidence interface from its current single-book HTML pilot to
approved multi-source/page/structured units using the same explicit vehicle
scope. Pack bounded evidence with applicability decision/reason, unresolved
qualifiers, original citation, content/source hashes, native/OCR provenance,
review revision and complete required context. Separate background reference
and possible matches from approved actionable units. A vehicle match alone is
not approval of a diagnostic step.

Test deterministic query/evidence scenarios and citation resolution before
adding a provider. Retain stale-source rejection and rejection of stale review
decisions. Verify that expansions, reranking, snippets, future embeddings and
tool calls cannot broaden the approved scope. Embeddings and provider/API/chat
integration remain separately selected work with their own measured benefit.

**Pass:** evidence is bounded, reproducible and traceable; excluded material
never enters a packet; changing a source, policy or review invalidates affected
packets; reviewed structured examples meet B1 criteria. Produce the expanded
extraction acceptance report and the concrete remaining AI integration tasks.

## 7. Acceptance matrix shared by all implementations

Use small authored fixtures in Git and the reviewed local equivalents. Include
a synthetic car from a make absent from today's manual collection to catch
hardcoded Ford/GM assumptions. Do not use model output as its own ground truth.

| Test | Required outcome |
| --- | --- |
| Ford Super Duty 6.0 diesel query with GM 6.0 gasoline present | GM-only index/text is never visited; no equal-displacement engine merge. |
| Lincoln/Mercury book from a Ford disc | Source publisher does not become vehicle make; correct canonical brand or explicit unknown. |
| Correlated model/year/engine alternatives | No unsupported Cartesian combination is generated. |
| Empty make/engine vs explicit all-engine statement | Unknown remains unconfirmed; explicit-all retains its bounded source scope. |
| Confirmed book with contradictory page/table/caption | Child restriction is evaluated; parent does not bypass it. |
| Unclear first-page PDF applicability | Not promoted to the entire PDF without evidence of scope. |
| Shared F-250/F-350 section | Both explicit/reviewed targets match; F-150 is not inferred. |
| Same part, same text or identical image in different manuals | Relationship remains a proposal; no automatic procedure applicability. |
| Pending cross-make proposal | Visible for review; absent from vehicle-confirmed search and evidence. |
| Rejected/revoked/stale review | Current app/rebuilt exports exclude it; disconnected old exports explicitly label their decision revision/date rather than claiming current approval. |
| Revoke approval, then fail index rebuild | The old content stays readable; the revoked search eligibility is not restored. |
| Mixed-engine PDF table and OCR qualifier error | Search only reliably isolated eligible text; otherwise omit the page from engine-filtered text search and retain metadata navigation/original reading. No wrong row becomes an approved fact. |
| Generic DTC reference and owner guide | Clearly typed and scoped; neither establishes workshop/repair coverage. |
| No eligible units or missing required vehicle data | Clear empty/possible state; no fallback to whole-library text search. |
| Excluded items dominate first 100 global hits | Valid scoped results remain discoverable because scoping precedes limits. |
| Legacy PDF, conflicting-book panel, literal fallback | Every route honors the same pre-search allowlist. |
| Prefix queries, snippets, counts, browser caches | Excluded data does not influence active search or appear after scope changes. |
| Multiple books of one role; ZIP/folder copies; changed editions | No overwritten books, collapsed citations or automatic review transfer. |
| Failed import, migration or viewer build | Previous content remains available; search fallback requires still-valid review/policy eligibility; originals unchanged. |
| Offline browser and source links | No remote assets required; links, captions and return state work at narrow widths. |
| Structured value/step lacking reliable context | Abstain or mark incomplete; do not invent units, branches or fitment. |

## 8. How to run this plan in separate tasks

The planning branch contains documents only. Start each implementation branch
from the latest accepted dependency state, preserving unrelated local edits.
Use a clean worktree for Repair Buddy rather than switching its dirty main
checkout. Keep the toolkit separate. Record/pin dependencies between repositories
and push each completed commit to its corresponding remote branch, as requested.
Merging a future feature or creating a public release needs its own instruction.

For an extractor code step, run the existing unittest suite and Ruff plus the
new targeted contract/behavior tests. Enable `jsonschema` and the Poppler tests
when testing those paths. For an application step, run Repair Buddy's suite,
Ruff, migration/retrieval tests and relevant browser checks. Browser steps need
actual interaction/network-observation checks, not only source-text assertions.
Documentation-only steps need link, consistency and diff checks rather than
rerunning extraction or OCR. Baseline Step 8 counts were 134 extractor and 234
Repair Buddy tests; later totals should grow, not be treated as fixed targets.

Keep detailed logs and manual examples outside Git. Summarize completed gates,
exact revisions, pending input paths and the next selected task in the handoff.
Stop on a failed gate and explain the actual failure; do not silently skip the
gate and continue through several steps to spend the remaining budget.

Reusable task prompt:

> Implement step A<N> (or B<N>) from docs/VEHICLE_MANUAL_APPLICABILITY_PLAN.md
> only. Read the current handoff and this step's prerequisites. Verify branches,
> dependency revisions and relevant input identities; preserve unrelated local
> edits and keep manual data outside Git. Implement its deliverables, run its
> pass gate, record results, commit and push the completed work. Stop before
> the next step. Finish with what changed, verification and unresolved issues,
> followed by a detailed description of the next step and its recommended model
> and reasoning level.

## 9. References for implementation

- [Frozen extraction contract](SERVICE_MANUAL_CONTRACT_V1.md),
  [normalization behavior](CONTENT_NORMALIZATION_V1.md),
  [shared viewer](SHARED_VIEWER_V1.md), and
  [previous release checkpoint](STEP8_RELEASE_CHECKPOINT.md).
- Extractor: `sme/source.py` (detection), `sme/contract.py` (IDs/schema semantics),
  `sme/normalize.py` (PDF publication evidence and aliases),
  `sme/html_content.py`, `sme/pdf_content.py`, `sme/viewer.py`,
  `fsd/build.py` (legacy role selection), `viewer/assets/app.js` (global ranking).
- Repair Buddy: `src/repair_buddy/vehicles.py`, `database.py`, `applicability.py`,
  `catalog.py`, `source_library.py`, `source_ingestion.py`, `retrieval.py`,
  `app.py`, `sources/service_manual_package.py`, and `rag/`.
- Repair Buddy design/acceptance: `docs/project-design.md`,
  `docs/applicability-parity-acceptance.md`,
  `docs/service-manual-package-integration.md`,
  `docs/pilot-rag-implementation-plan.md`, and the Ford inventory/coverage audit
  documents reconciled during A1.

Historical documents sometimes describe an earlier implementation stage. Use
the verified code, source identities and this plan's explicit proposed behavior
to distinguish what already works from what still needs implementation.
