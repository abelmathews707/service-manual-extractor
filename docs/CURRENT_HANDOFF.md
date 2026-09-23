# Service Manual Extractor — current handoff

Updated: 2026-09-23
Current checkpoint: Step 4 content normalization is implemented. The seller PDF
set produced 12,324 cited searchable pages. Synthetic HTML gates and sampled
source checks pass; full HTML browser/visual acceptance and complete-source
acceptance remain open. Application integration has not started.

## Start here

1. Read the [seller PDF inspection record](GM_PDF_SELLER_COLLECTION.md).
2. Read the [GM HTML USB inspection](GM_HTML_INSPECTION.md), especially the
   unresolved source-integrity findings.
3. Read the frozen [shared extraction contract](SERVICE_MANUAL_CONTRACT_V1.md).
   Read the [Step 4 behavior and limitations](CONTENT_NORMALIZATION_V1.md).
4. Select one remaining step from the [GM manual-input implementation plan](GM_HTML_PLAN.md).
5. Read that step's [test gate](GM_HTML_TEST_PLAN.md).
6. Verify branches, working-tree changes and exact input identities before acting.

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
| Feature branch | `codex/gm-html-manuals` |
| Branch baseline | `f1bdc8d`, main and `v0.1.0` foundation |
| Upstream | `https://github.com/shad0wca7/ford-service-disc.git` |
| Compatible existing command | `python -m fsd` |
| Neutral source command | `python -m sme` (`probe`, staged `extract`, `normalize`, contract validation) |
| Repair Buddy | `/Users/asokmathews/Documents/repair-buddy`, main `57eba8f` |
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

| Input | Local root | State |
| --- | --- | --- |
| Original GM USB HTML exports | `/Users/asokmathews/Documents/service-manual-data/gm-usb-2026-09-15` | Copied and inspected; damage/instability documented; replacement still needed for real-source acceptance |
| Seller GM PDFs | `/Users/asokmathews/Documents/service-manual-data/gm-seller-download-2026-09-17` | Original folder and ZIP preserved; independent archive extraction and file parity verified |

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
- The working Ford `fsd` interface is unchanged. Repair Buddy integration
  remains a later step.

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
  neutral CLI tests. Step 4 expands the suite to 128 tests; integration tests
  remain planned.

## Next task

**The original HTML USB Step 1 blocker remains:** obtain a reliable seller or
download replacement before claiming real-source acceptance for those HTML
manuals. Do not repeat unbounded repair attempts against the unstable USB.

**The next implementation milestone is Step 5: Repair Buddy integration.**
Read the Step 4 content guide before consuming the package. Start a separate
Repair Buddy branch from its then-current main and preserve local edits. Use a
disposable test database, keep native/OCR provenance and original citations, and
honor content-processing status, search eligibility and unavailable assets/links.
Complete the outstanding HTML visual/browser acceptance when an allowed browser
environment is available; do not treat sampled structural checks as that gate.

Do not treat folder names as vehicle coverage, flatten tables into ambiguous
text or parse the damaged HTML ZIPs as complete inputs. Repair Buddy integration
remains Step 5 and must use a separate branch in that repository.

The completed local OCR output remains derived, not source truth. Retain
per-page source identity and native-text/OCR provenance; generic source qpdf
warnings are review metadata, not automatic source rejection.

Model recommendations are in the step table: Terra Medium for routine adapter
work, Sol Medium/High for structure/integration, Luna Low for mechanical
checks/docs, and Astra High only for difficult unresolved design/review.
