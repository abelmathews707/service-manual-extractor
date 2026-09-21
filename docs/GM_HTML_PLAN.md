# GM manual inputs and multi-format extractor plan

Date: 2026-09-21
Status: Steps 0–2 complete. Implement one later selected step per task.

## Outcome

A user selects their vehicle, searches manuals, opens a cited procedure, follows
references, enlarges diagrams, and returns to the results through the same Repair
Buddy interface for Ford and GM. Manufacturer differences belong in the source
adapters and manual evidence, not separate application screens.

The extractor repository is now
[abelmathews707/service-manual-extractor](https://github.com/abelmathews707/service-manual-extractor).
The local checkout remains `/Users/asokmathews/Documents/ford-service-disc` so
existing Repair Buddy settings continue to resolve. The branch is
`codex/gm-html-manuals`, based on `main` at
`f1bdc8d` (the extractor's `v0.1.0` foundation). Upstream remains
`shad0wca7/ford-service-disc`; retain its history and independent updates.

This plan does not implement AI diagnosis. Repair Buddy's existing applicability
and grounded-assistant milestones still apply to every make.

## Evidence that drives the design

See [HTML USB inspection findings](GM_HTML_INSPECTION.md) and the separate
[seller PDF inspection record](GM_PDF_SELLER_COLLECTION.md) for integrity
results and local paths. Neither input is a Ford archive.

- Three ZIP labels: GMC Sierra 2500 HD 6.0L, 6.6L, and 8.1L, allegedly 2001–2006.
- Readable 6.6L and 8.1L index pages identify 2006 vehicles. Earlier-year coverage
  is unverified. The ZIP names are source labels, not applicability evidence.
- Root `index.html`, numeric `pages/*.html`, local `images/` and `icons/`, and a
  small folding-navigation script. The content does not require JavaScript.
- Large navigation trees, repeated content under different paths, short leaf
  headings, and pages explicitly warning about a different vehicle are present.
- Wiring diagrams include SVG; captions often precede their image. Diagnostic
  tables carry Step/Action/Values/Yes/No relationships that must survive import.
- Archive integrity problems are a separate source issue. Extracting readable
  members does not establish a complete or trustworthy manual.
- The seller PDF set is intact but is a patchwork of articles, not a complete
  vehicle/year library. Its PDF source identities, page counts, title evidence
  and native-text/OCR status must stay attached to every derived record.

## What to reuse and what to add

| Layer | Reuse | New work |
| --- | --- | --- |
| Ford extraction | `fsd/arc.py`, `disc.py`, `idicomp.py`, `iso.py`; existing CLI/probe contracts | A compatibility bridge to a neutral contract only when required |
| HTML export extraction | Standard ZIP reading and the repository's synthetic-test approach | Format detection, directory-preserving extraction, manifests, integrity reporting |
| PDF collections | Existing generic PDF/source ideas in Repair Buddy and local workshop-toolkit OCR flow | Collection manifest, file/page identities, native-text/OCR provenance and page citations |
| Repair Buddy catalog/import | `sources/base.py`, `source_library.py`, ingestion staging and recorded dependency revisions | HTML export adapter and adapter dispatch in place of Ford-only import entry points |
| Search and citations | Normalization, full-text index, content identities, citation checks | Navigation exclusion, hierarchy/context, aliases and applicability qualifiers |
| Reader and diagrams | `references.py`, `safe_html.py`, existing reader, gallery and return navigation | GM caption association and checked SVG support |
| Standalone extractor viewer | Static assets, search and backlink ideas | Neutral content input; current `.EPL`/SERVICE/EVTM/PCED builder cannot consume GM exports directly |

Do not use Ford's `extract.safe_name()` for ZIP paths: it flattens names and
would destroy nested paths and duplicate basenames. Do not fabricate `.EPL`
files or pretend GM books are Ford `SERVICE`, `EVTM`, or `PCED` archives.

## Proposed format boundary

Detect formats from their structure, not the car badge. The first additional
format is provisionally `workshop_manuals_html_v1`, based on the observed HTML
export layout. A separate provisional `pdf_collection_v1` describes an
identified folder/ZIP of PDFs with per-file and per-page evidence. Neither name
is a promise that every GM or other-manufacturer publication uses that format.

Keep `python -m fsd`, its JSON schema and exit behavior, `--book`/`--archive`,
Repair Buddy's stored `ford_disc` IDs, and `[ford_disc].path` compatible.
Introduce a neutral entry point, provisionally `python -m sme`, without renaming
the existing `fsd` package in one large rewrite. Final naming and schema are the
deliverable of Step 2.

The neutral manifest should be versioned and carry:

- Source format, original archive SHA-256, source-relative archive identity,
  extractor version/revision, extraction status and all failures.
- Book identity independent of title; selected root and entry page; original
  label separately from verified or source-claimed vehicle metadata.
- Document IDs scoped to their book, original relative paths and file hashes,
  title, breadcrumb hierarchy, content role, anchors and outgoing references.
- Asset paths, MIME/type, hashes, captions and relationships to documents.
- For PDF collections: original per-file hash, page count, title/first-page
  evidence, page-level citations, and whether text is native or OCR-derived.
  An OCR output must point to the untouched original and record its own hash.
- Explicit applicability evidence and level (book, page, table, caption),
  conflicts, exclusions and unknowns. Keep engine/RPO strings as supplied.
- Aliases for repeated procedure content, retaining every original citation.
- Missing-target records that distinguish omitted other-vehicle content,
  absent source files, rejected files, failed extraction and unsupported views.

Repair Buddy owns normalized fragments, indexes, retrieval ranking, cases, AI
responses and the application UI. The extractor owns format reading and
faithful export metadata. It does not write Repair Buddy's live database.

## Sequential steps

The recommendations below are task-specific judgments, not promised credit
costs. Use the lowest effort that passes each gate. Current official guidance
positions Luna for clear repeatable tasks, Terra for everyday work, Sol for
complex work and Astra for the hardest workflows; higher effort uses more
tokens. [OpenAI model guidance](https://learn.chatgpt.com/docs/models).

| Step | Deliverable and stop point | Suggested model/effort |
| --- | --- | --- |
| 0 — Inspect and preserve | Local copies, extraction/integrity reports, findings, this plan; completed investigation with source problems documented | Current task |
| 1 — Resolve input integrity | Obtain or establish verified originals; record exact surviving/missing files, source completeness and a representative fixture inventory | Terra Medium; Luna Low for rerunning established commands |
| 2 — Freeze the common contract | Approve neutral manifest/CLI and synthetic fixtures; preserve old Ford behavior in contract tests | Sol Medium; Astra High only if architecture issues remain |
| 3 — ZIP/folder extraction | Implement bounded, repeatable extraction and format probing with machine-readable failures and source identities | Terra Medium; Sol High for unresolved archive/path failures |
| 4 — HTML meaning and diagrams | Extract hierarchy, procedures, references, qualifiers, tables and diagram/caption relationships; implement safe SVG handling | Sol High |
| 5 — Repair Buddy integration | Common import dispatch, selected publications, normalization/search, citations, reader and diagram flow | Sol Medium or High |
| 6 — Ford/GM acceptance | Run the same user tasks and applicability checks on both; resolve regressions and document limitations | Sol High; Astra High for an unresolved cross-layer review |
| 7 — Standalone viewer parity | Feed the extractor's static viewer from neutral records; verify both brands with the same viewer interactions | Terra Medium; Sol High if the viewer boundary needs redesign |
| 8 — Release checkpoint | Document supported formats/verified coverage, dependency revisions and setup; prepare a reviewable release candidate | Luna Low for docs/checks; Terra Medium for fixes |

Step 8 is an engineering checkpoint. Public commercialization remains a
separate deferred Repair Buddy milestone. Do not bundle manuals with a release.

### Step 1 — Resolve input integrity

Revisit the inspection report before another full scan. Preserve original
copies, hashes and the failed-file lists. Compare a replacement/re-copied ZIP
against its source, then read every member and verify size and CRC. A rebuilt
directory or partial recovery remains a derived artifact with a separate hash.
Never splice files from another engine's archive based only on matching names.

If HTML originals remain damaged, record that limitation and use synthetic
fixtures to develop Steps 2–5. The separately verified PDF set is usable for
local acceptance candidates but does not fix the HTML inputs or establish its
own complete vehicle coverage. Real-manual completion and release gates stay
open. The user need not spend repeated agent runs rediscovering the same damage.

Pass: source/copy integrity and per-member results are reproducible, with known
coverage and any unrecoverable gaps explicitly resolved or blocked.

### Step 2 — Common contract and synthetic fixtures (complete 2026-09-21)

Define format detection, exact book selection, machine-readable probe/extract
results, manifest schema, neutral command names, stable IDs, path handling and
failure states. Add tiny authored HTML/SVG examples and generated PDF examples:
an index, numeric page paths, duplicate navigation routes, a qualifier warning,
a diagnostic table, raster/SVG diagrams, native/OCR page provenance and a
missing-content placeholder.
Identical procedure text with different applicability qualifiers must retain
its separate context and citations rather than being merged into one claim.

Freeze representative Ford CLI JSON and selection behavior. Keep `fsd` working
and retain historical provenance even after a repository URL changes. Do not
rewrite the original tagged `v0.1.0` release or silently update consumers.

Pass: synthetic contracts and existing Ford tests pass; the output contract is
documented enough for the Repair Buddy adapter to consume independently.

Implemented result: `service-manual-manifest/v1` and
`service-manual-operation/v1` are frozen in
[`SERVICE_MANUAL_CONTRACT_V1.md`](SERVICE_MANUAL_CONTRACT_V1.md), the JSON
Schema and dependency-free validator. The contract covers Ford v1/v2, HTML
exports and PDF collections, including stable IDs, exact paths, partial-source
failures, qualifiers, citations, assets and native/OCR text provenance. Authored
HTML/SVG/raster examples and a generated PDF exercise the rules. Existing
`fsd` command names, probe JSON/exit behavior and exact duplicate-archive
selection remain unchanged. The neutral CLI exposes contract inspection and
manifest validation only; real neutral source readers remain Step 3 work.

### Step 3 — source containers and extracted-folder reader

Add explicit format probing for ZIPs and already-unpacked roots. Preserve
relative paths; detect unsafe names, symbolic links, case/Unicode collisions,
encrypted/unsupported inputs, corrupt entries and resource-limit violations.
For PDF collections, record file hashes/counts/page counts and do not infer
vehicle coverage from a folder name. Use staged output and hashes, and make
interruption/re-run behavior explicit. Recovery must be a separate operation
with a separate output/status.

Pass: test cases in the test plan pass; a valid ZIP and its unpacked equivalent
describe the same content, with distinct container provenance. No silent skips
or successful completion status after unreadable required files.

### Step 4 — HTML structure, PDF pages, context and assets

Use `.main`, page headings and breadcrumb hierarchy rather than indexing the
entire website shell. Detect structural navigation, root/index duplicates,
`404.html`, `external-car.html`, footer links, leaf sections and procedure aliases.
The parent DTC and diagnostic branch must remain connected to a short leaf page.
Retain original HTML for checked reading and preserve diagnostic table structure
for future evidence packing; flattened text alone is insufficient.

Associate `.imageHeader .imageCaption` with its following `.imageHolder` image.
Make SVG handling explicit: validate references and active content, then render
through a reviewed safe policy or locally generated preview while retaining the
original hash. Do not enable arbitrary source scripts or external requests.
Extract vehicle mismatch warnings and engine qualifiers at their actual level.

Pass: selectors, hierarchy, aliases, tables, qualifiers, captions and SVG tests
pass. Representative local source pages match the derived records visually and
structurally. All unresolved links are classified.

For PDF collections, retain the PDF as the canonical reader source. Extract
page-based searchable text, title/applicability evidence and page assets without
inventing a document hierarchy. Route native text and OCR-derived text through
the same search contract while recording the provenance difference. A page-level
citation must resolve to the correct original file and page.

### Step 5 — Repair Buddy integration

Start a separate Repair Buddy feature branch from its then-current `main` and
preserve existing local edits. Implement source adapters behind the application's
existing source interfaces. Generalize Ford-wired import dispatch, failure
checks and dependency provenance without changing existing Ford IDs. The first
adapters may be HTML export and PDF collection; do not create separate
manufacturer-specific application flows.
Reuse ingestion staging, transactions and rollback behavior.

Use the same vehicle selection, matching sections, citation route, reader,
gallery and return navigation. Let available capabilities and metadata drive
behavior. Index a separate disposable test database first. Do not feed unreviewed
GM evidence to diagnosis or weaken the existing applicability work.

Pass: common app flows work for both source types; old Ford records still open,
and failed imports preserve existing searchable content.
Test missing-image and missing-HTML/navigation inputs separately. If incomplete
manual browsing is supported, label it explicitly and preserve precise missing
file reasons; it must never acquire a complete-coverage or diagnosis-ready status.

### Step 6 — Applicability and parity acceptance

Use the test matrix and reviewed known-answer pages. A 2006 label must not
authorize 2001–2005 procedures. A 6.6L/8.1L book must not silently recommend a
6.0L CNG circuit or the Sierra 1500 labor specification. Matching book titles
do not resolve contradictory page/caption qualifiers.

Pass: same interaction contract for Ford and GM, citations resolve to the
correct source/variant, navigation and diagrams work, partial data is visible,
and no old Ford regression remains. This establishes retrieval/reader quality;
diagnostic accuracy still requires the later assistant evaluation.

### Steps 7–8 — Standalone viewer and release

Standalone viewer parity is separate from Repair Buddy parity and belongs here
so it is not accidentally assumed complete. Convert neutral records to the
shared viewer's document/search/navigation model; do not route GM through the
Ford `.EPL` parser. Generalize labels and support multiple books without the
current first-book-per-role limitation. Verify links, search and offline assets.

Prepare release notes naming supported formats, verified vehicles/years,
partial/unsupported features, reproducible test commands and both repositories'
dependency revisions. Review commits before any merge/tag/public release.

## How to resume with limited credits

Start a new task for one step. Read only the handoff, relevant step and tests,
then stop at its pass gate. Keep counts and logs in local artifacts, summarize
them, and avoid repeatedly loading tens of thousands of manual pages into the
conversation. Prefer deterministic commands for inventory/extraction. Use
agents only for a bounded independent review where the benefit justifies it.

Reusable prompt:

> Continue service-manual-extractor from docs/CURRENT_HANDOFF.md. Work on Step N
> of docs/GM_HTML_PLAN.md only. Read its corresponding tests in
> docs/GM_HTML_TEST_PLAN.md. Verify branch/status and recorded input integrity.
> Preserve source files and Ford compatibility. Implement and verify this step,
> update the handoff with results and remaining issues, then stop before the
> next step. Keep manual data outside Git.
