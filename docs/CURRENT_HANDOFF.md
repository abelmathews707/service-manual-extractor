# Service Manual Extractor — current handoff

Updated: 2026-09-25
Current checkpoint: Steps 0–8 are implemented. The seller PDF set produced
12,324 cited searchable pages, Repair Buddy imports and labels GM evidence, and
the extractor now builds the shared offline viewer directly from neutral
records. The user reports that replacement GM HTML files have been obtained;
their integrity and coverage have not yet been checked in this repository.
The completed code was merged into extractor `main` at `9341637` and Repair
Buddy `main` at `310ce81`; no public release was created. See
[the release record](STEP8_RELEASE_CHECKPOINT.md).

The new [vehicle manual applicability plan](VEHICLE_MANUAL_APPLICABILITY_PLAN.md)
covers all available formats, shared vehicle mapping/review, pre-search filters,
Repair Buddy and the offline viewer. Phase A delivers searchable/manual content;
Phase B adds structured extraction. It is design only, on
`codex/vehicle-manual-library-plan`. Step A1 is complete; the next task is
**A2**, not another step from the completed GM sequence.

## Start here

1. Read the [current vehicle mapping plan](VEHICLE_MANUAL_APPLICABILITY_PLAN.md)
   and select one A/B step. Do not implement several steps on a generic continue.
2. Read the [seller PDF inspection record](GM_PDF_SELLER_COLLECTION.md).
   The [GM HTML USB inspection](GM_HTML_INSPECTION.md) is historical; the user
   has obtained replacements and the old damage is not a project blocker.
3. Read the frozen [shared extraction contract](SERVICE_MANUAL_CONTRACT_V1.md).
   Read the [Step 4 behavior and limitations](CONTENT_NORMALIZATION_V1.md).
4. Read the [shared viewer behavior](SHARED_VIEWER_V1.md).
5. Use the completed [GM manual-input implementation plan](GM_HTML_PLAN.md)
   for background only.
6. Read the selected A/B step's pass gate and shared acceptance matrix in the
   new plan; retain existing [regression gates](GM_HTML_TEST_PLAN.md).
7. Verify branches, working-tree changes and exact input identities before acting.

The user wants the same Repair Buddy experience across makes, with the manuals
providing the content. Work is intentionally split into small sequential tasks
to manage Codex usage. Do not implement all steps on a generic “continue.”

User preference recorded 2026-09-23: push new commits to the corresponding
remote branch after committing. Report any push failure; this does not authorize
force-pushing, merging, tagging or releasing.

## Repository state and compatibility

| Item | State at this checkpoint |
| --- | --- |
| GitHub fork | `https://github.com/abelmathews707/service-manual-extractor` |
| Previous fork name | `abelmathews707/ford-service-disc` |
| Existing local checkout | `/Users/asokmathews/Documents/ford-service-disc` |
| Planning branch | `codex/vehicle-manual-library-plan` |
| Planning baseline | merged main `9341637306af6595ab4233b39db7f80693d7069b` |
| Upstream | `https://github.com/shad0wca7/ford-service-disc.git` |
| Compatible existing command | `python -m fsd` |
| Neutral source command | `python -m sme` (`probe`, staged `extract`, `normalize`, `build-viewer`, contract validation) |
| Repair Buddy integration checkout | `/Users/asokmathews/Documents/repair-buddy-step5`, merged feature tip `4076bec`; remote main `310ce81` |
| Workshop toolkit | `/Users/asokmathews/Documents/workshop-manual-toolkit-main`, main `d150e7d` |

GitHub was renamed with the user's chosen name. The local `origin` URL was
updated and fork/upstream identity verified. The local folder and `fsd` package
retain their names so Repair Buddy's existing dependency configuration works.
Other historical docs/records may still use the old repo name; do not rewrite
old provenance or mass-rename paths. No original release tag was changed.

Repair Buddy has three pre-existing documentation edits on main (`README.md`,
`docs/current-handoff.md`, `docs/project-design.md`) recording a deferred
commercial-release milestone. This task did not modify those files. Create a
separate branch for the later Repair Buddy integration and preserve that work.
The workshop toolkit is independently versioned; do not mix its changes into
this repository.

## Local manual data

All source files and detailed reports are outside Git.

A1 metadata summary is in [A1_INVENTORY_SUMMARY.md](A1_INVENTORY_SUMMARY.md).
Detailed local inventory and citation cases are under
`/Users/asokmathews/Documents/service-manual-data/a1-inventory-2026-09-25/`.
The replacement GM HTML source path remains to be recorded when available.

| Input | Local root | State |
| --- | --- | --- |
| Original GM USB HTML exports | `/Users/asokmathews/Documents/service-manual-data/gm-usb-2026-09-15` | Earlier copies were damaged; user reports replacement files are now available, but their path and integrity have not yet been recorded here |
| Seller GM PDFs | `/Users/asokmathews/Documents/service-manual-data/gm-seller-download-2026-09-17` | Original folder and ZIP preserved; the 113-PDF folder moved from Downloads is under `from-downloads/` and matches `from-archive/` exactly; it contains no HTML/HTM |

No data was added to Repair Buddy's live database. Tests must synthesize small
inputs; vendor manuals, PDFs, ZIPs and large derived output stay out of Git.

## Important findings

### Step 2 shared contract: complete

- `service-manual-manifest/v1` records exact source identity, completeness,
  publications, documents, qualifiers, citations, links, assets and text provenance.
- `service-manual-operation/v1` defines the neutral probe/extract JSON now used
  by `sme probe` and `sme extract`.
- Stable IDs are derived from immutable source identity and canonical
  source-relative paths. Duplicate short codes or filenames are not selectors.
- Unknown formats are rejected. Partial inputs require exact failure records;
  OCR text remains derived from and cited back to the original page.
- Authored HTML/SVG/raster examples and an in-memory generated PDF cover
  qualifiers, diagnostic tables, repeated wording with separate context,
  missing content, page citations and native/OCR provenance.
- The working Ford `fsd` interface is unchanged. Repair Buddy integration was
  added later in Steps 5–6 without routing neutral input through Ford parsing.

### Step 3 source reader: complete

- `sme probe` fully reads and hashes supported ZIPs, unpacked folders and PDFs,
  verifies PDF page counts and returns exact selectable publication IDs.
- Archive guards cover traversal/absolute/drive/backslash/control paths,
  symlinks, encryption, compression types, duplicate/case/Unicode collisions,
  corruption and configured expansion limits.
- ZIP and folder inputs retain different container provenance while a canonical
  file inventory proves whether their content is identical.
- `sme extract` copies exact selections into a fresh sibling staging directory,
  verifies bytes/hashes, writes the common manifest plus raw-file inventory and
  atomically publishes. Partial sources and interrupted runs never publish.
- The preserved seller ZIP and its matching unpacked root each report 113 PDFs,
  12,324 pages and content SHA-256
  `b88d90f9675e18fd241eb8653d3b24de2d6232d749aacc1a999ccd80eb105a4a`.
- The original 6.6L and 8.1L ZIPs reproduce 760 and 5,483 exact failures. The
  6.0L ZIP is rejected for corrupt directory/extra-field structure.

### Step 4 content normalization: implemented; HTML acceptance limited

- `sme normalize` verifies a Step 3 extraction and publishes original files,
  the populated v1 manifest, the original inventory and a versioned content file.
- HTML records retain content roles, breadcrumbs, navigation routes, tables,
  warnings, qualifiers, references, captions and static SVG derivatives.
- Every PDF page has its own document ID and exact original-file/page citation.
  Original text takes precedence; OCR is accepted only with matching original
  and derived hashes, page counts and recorded tool/version.
- Local acceptance: 113 PDFs, 12,324 searchable pages (7,606 native, 4,718 OCR),
  zero processing failures, unchanged original hashes. Detailed output remains
  under `gm-seller-download-2026-09-17/step4-acceptance/`, outside Git.
- 128 tests pass with Poppler/schema checks enabled. Eleven hash-checked HTML
  samples and one offline-rendered sanitized SVG were reviewed. Browser policy
  blocked the HTML preview, so full HTML visual/browser acceptance remains open.
- PDF pages are retained whole for layout/diagrams; PDF table inference and
  embedded-image extraction are not claimed. OCR correctness still needs review.
- See [CONTENT_NORMALIZATION_V1.md](CONTENT_NORMALIZATION_V1.md) for commands,
  schemas, source/status distinctions and remaining limitations.

### Steps 5–6 application integration and acceptance: complete

- Repair Buddy consumes neutral HTML/PDF records through its existing source,
  search, citation and reader interfaces without changing historical Ford IDs.
- Vehicle-selected search distinguishes confirmed, candidate, reference and
  conflict states; free-form GM labels never become confirmed coverage.
- The acceptance checkout passed 234 tests and Ruff. The extractor correction
  for an owner-manual false positive passed 130 tests with one optional skip and
  Ruff at `ad550c5d`.
- Detailed acceptance data remains outside Git under
  `/Users/asokmathews/Documents/service-manual-data/step6-acceptance-2026-09-23`.
- See Repair Buddy's `docs/applicability-parity-acceptance.md` in the integration
  checkout for the exact known-answer and browser results.

### Step 7 shared offline viewer: complete

- `sme build-viewer NORMALIZED -o SITE` validates the normalized package and
  atomically publishes a static site.
- The neutral path does not invoke the Ford `.EPL` parser. Both the existing
  Ford builder and neutral builder copy the same generalized viewer shell.
- All selected publications remain independently selectable and searchable.
  Nested routes, resolved links, backlinks, search-return state, captions,
  diagrams, exact local PDF page links and text provenance are retained.
- Missing, unsupported and blocked references/diagrams are visible. Source HTML
  and scripts are not copied into executable viewer pages.
- Real-data acceptance built all 113 reviewed GM publications and 12,324
  searchable pages with zero reported failures. Browser checks covered the
  library, a 179-result search (with its 150-row display cap labeled), a PDF
  page, return-to-search state and the phone-width navigation drawer.
- See [SHARED_VIEWER_V1.md](SHARED_VIEWER_V1.md) for commands, boundaries and
  verification.

### USB HTML exports: unresolved source integrity

- Three ZIPs labelled 6.0L, 6.6L and 8.1L contain ordinary HTML exports with
  local images, SVG wiring, navigation trees and diagnostic tables.
- Readable indexes identify 2006 vehicles, not validated 2001–2006 coverage.
- 6.6L: 60,009 valid files extracted; 760 image files fail.
- 8.1L: 54,998 valid files extracted; 5,483 HTML files fail.
- Both copies match their USB SHA-256; the source archives are damaged.
- 6.0L produces different USB-read hashes. Its preserved copies and recovery
  attempt have invalid directory data; no complete 6.0L extraction is available.

### Seller PDFs: validated input, limited coverage

- 113 PDFs / 12,324 pages match exactly between the supplied folder and ZIP.
- 39 PDFs have native selectable text (7,606 pages); 74 scanned PDFs (4,718
  pages) now have separately derived, validated searchable copies. All PDFs are
  readable and unencrypted.
- Source titles show a patchwork of 2000–03 GM truck/SUV articles, a 2004
  Silverado owner manual and a 2006 Silverado/Sierra article set. The folder
  labels do not prove all stated years or vehicle coverage.
- The PDFs are not a complete library for every 1998–2007 GM vehicle, and they
  do not establish production importer or diagnosis readiness.

## Verification performed

- Copied all five original USB files; performed source/copy hash checks and a
  separate 6.0L recopy/recheck.
- Read/CRC/length-checked every listed file in the 6.6L and 8.1L archives,
  extracted successful members and saved exact failures and file manifests.
- Copied the seller PDF folder and ZIP; tested every ZIP member; extracted all
  113 members; compared their SHA-256 values to the supplied folder; inspected
  PDF metadata, text coverage, representative rendering and title-page OCR.
- Used the independently versioned workshop toolkit through a local PDF/A
  compatibility runner to make all 74 scanned PDFs searchable. Every output is
  qpdf-clean, has the source page count and has per-page text; a final SHA-256
  pass confirmed that all 113 originals remain unchanged.
- Inspected source pages, scripts/styles, navigation, procedures, tables,
  diagrams and source warnings in the HTML set. This was not a full
  browser/diagnostic acceptance test.
- Step 3 extractor suite: 100 tests passed, including all previous Ford/contract
  tests plus source safety, repeatability, page-count, staging, selection and
  neutral CLI tests. Step 4 expanded the suite to 128 tests. The Step 7 gate
  passes 134 tests with one optional schema test skipped, and Ruff passes.
- The Step 7 generated-site audit found no missing local PDF/diagram targets,
  hash mismatches, external fragment links or remote runtime assets.

## Next task

Step 8 passed its fresh-checkout tests and release checks, and both feature
branches were merged. **A1 inventory reconciliation and acceptance-case
selection are complete**; see [the summary](A1_INVENTORY_SUMMARY.md) and
local-only evidence folder above. The replacement GM HTML path is still pending.
Next implement **A2: freeze the vehicle/applicability contracts** from
[the new plan](VEHICLE_MANUAL_APPLICABILITY_PLAN.md). The owner selected the
full app/viewer experience, possible shared-part matches requiring review, and
ordinary manual content before expanded structured data.

The old USB failure record remains historical evidence, not a blocker to this
code merge: the user reports that replacement GM HTML files are available.
Before claiming complete HTML coverage, record the replacement path, verify
its source hashes and every file, and run a separate real-source acceptance.
Do not describe the old recovered folders as diagnosis-ready.

The completed local OCR output remains derived, not source truth. Retain
per-page source identity and native-text/OCR provenance; generic source qpdf
warnings are review metadata, not automatic source rejection.

Recommended for A2: GPT-6 Sol High; each step and its rationale are in the plan.
