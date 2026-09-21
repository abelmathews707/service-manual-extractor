# Service Manual Extractor — current handoff

Updated: 2026-09-21
Current checkpoint: the shared v1 extraction contract and synthetic acceptance
examples are complete. Two GM inputs were previously inspected; the seller PDF
set is verified, while the original USB HTML exports remain incomplete.
Production GM extraction/import support has not been implemented.

## Start here

1. Read the [seller PDF inspection record](GM_PDF_SELLER_COLLECTION.md).
2. Read the [GM HTML USB inspection](GM_HTML_INSPECTION.md), especially the
   unresolved source-integrity findings.
3. Read the frozen [shared extraction contract](SERVICE_MANUAL_CONTRACT_V1.md).
4. Select one remaining step from the [GM manual-input implementation plan](GM_HTML_PLAN.md).
5. Read that step's [test gate](GM_HTML_TEST_PLAN.md).
6. Verify branches, working-tree changes and exact input identities before acting.

The user wants the same Repair Buddy experience across makes, with the manuals
providing the content. Work is intentionally split into small sequential tasks
to manage Codex usage. Do not implement all steps on a generic “continue.”

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
| Neutral contract command | `python -m sme` (contract/validation only; no readers yet) |
| Repair Buddy | `/Users/asokmathews/Documents/repair-buddy`, main `d59c8c8` |
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
- `service-manual-operation/v1` freezes future neutral probe/extract JSON and
  reserves `sme probe` and `sme extract` for Step 3.
- Stable IDs are derived from immutable source identity and canonical
  source-relative paths. Duplicate short codes or filenames are not selectors.
- Unknown formats are rejected. Partial inputs require exact failure records;
  OCR text remains derived from and cited back to the original page.
- Authored HTML/SVG/raster examples and an in-memory generated PDF cover
  qualifiers, diagnostic tables, repeated wording with separate context,
  missing content, page citations and native/OCR provenance.
- The working Ford `fsd` interface is unchanged. Neutral source readers,
  normalization and Repair Buddy integration remain later steps.

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
- Step 2 extractor suite: 75 tests passed, including the previous Ford tests,
  neutral contract tests and frozen Ford command/JSON/exit behavior. New
  production reader, parser and integration tests remain planned.

## Next task

**The original HTML USB Step 1 blocker remains:** obtain a reliable seller or
download replacement before claiming real-source acceptance for those HTML
manuals. Do not repeat unbounded repair attempts against the unstable USB.

**The next implementation milestone is Step 3: source containers and the
extracted-folder reader.** Add explicit detection for ZIPs and already-unpacked
folders, safe staged extraction, collision/path/resource checks, deterministic
inventories and exact publication selection. For PDF collections, record file
hashes and page counts without inferring vehicle coverage from folder names.
Implement against synthetic inputs first, then perform local acceptance against
the verified seller files and readable HTML material without committing any
manual files.

Do not begin Step 4 HTML/PDF content normalization or Repair Buddy integration
as part of Step 3. Keep the original incomplete USB HTML state visible; a
successful partial read must not become a complete-source claim.

The completed local OCR output remains derived, not source truth. Retain
per-page source identity and native-text/OCR provenance; generic source qpdf
warnings are review metadata, not automatic source rejection.

Model recommendations are in the step table: Terra Medium for routine adapter
work, Sol Medium/High for structure/integration, Luna Low for mechanical
checks/docs, and Astra High only for difficult unresolved design/review.
