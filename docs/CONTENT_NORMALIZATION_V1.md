# Manual content normalization v1

Implemented for Step 4 on 2026-09-23. The neutral command turns a verified
Step 3 extraction into structured HTML records or individually cited PDF pages.
It keeps every original file and its source identity. Repair Buddy integration
is Step 5; the standalone viewer remains Step 7.

## Commands and output

```sh
python3 -m sme extract SOURCE -o verified
python3 -m sme normalize verified -o normalized --json
python3 -m sme normalize verified -o normalized-with-ocr \
  --ocr-manifest /path/to/ocr-map.json --json
```

Both output directories must be fresh. Normalization verifies the manifest,
inventory, publication selection and every selected file's hash/size, copies
originals into sibling staging, builds content, validates the result, and
renames staging into place. Exceptions or cancellation remove staging. Input
files are never edited. Input sources marked partial are refused.

The output contains:

- Original files at their original relative paths.
- `.sme-manifest.json`: existing v1 contract populated with cited documents.
- `.sme-source-inventory.json`: unchanged Step 3 source inventory.
- `.sme-content.json`: `service-manual-content/v1`, with searchable text,
  structured content, roles, references, navigation, figures and limitations.
- `.sme-derived/`: approved static SVG derivatives, named by their hash.

The content and OCR-map JSON Schemas are in `schemas/`. Existing manifest and
probe/extract operation schemas are unchanged. `normalize --json` has its own
summary (not the frozen probe/extract operation envelope).

Exit 0 means all selected documents were processed; it does not prove complete
vehicle coverage, perfect OCR, or zero missing source references. Exit 1 means
document processing failed and a **partial content package** was published with
exact failures and surviving documents. Exit 2 means the input, destination or
metadata could not be accepted. Source-integrity status and content-processing
status are separate: a valid original can contain unsupported markup or refer
to absent material. Consumers must inspect both statuses, link/figure states
and `search_eligible` before presenting content. The summary reports unresolved
references and unavailable figures even when processing completed.

## HTML fidelity and context

The parser reads static HTML without executing JavaScript. It prefers `.main`,
falls back to the body, and explicitly reports missing body/heading or rejected
encoding. UTF-8, Windows-1252 and ISO-8859-1 are supported. HTML is bounded to
32 MiB, 300,000 nodes and 200 levels. Common omitted list/table closing tags
from the observed exports are handled.

Header breadcrumbs, nested navigation folders (including anchors without an
`href`), alternate routes, named anchors and source link wording are retained.
Index/404 landing pages, copies of the landing page, navigation trees and the
publisher's `external-car.html` notice are not search procedures. Header,
branding, footer, navigation and active elements are excluded from searchable
procedure text. Footer links remain in the reference audit with a shell role.

The content `structure` is an ordered tree of approved tags and escaped-text
data. It retains headings, paragraphs, lists, tables, cells, headers and merged
cell spans. Links and figures refer to indices in their respective arrays;
they carry no executable source attributes. A consumer must build elements
from the allowlist and insert strings as text, never as raw HTML. Table text
can support search, but the table tree and original source govern the meaning
of Yes/No branches and values.

Applicability records retain literal source statements, scope and selectors:
document, table or figure. Breadcrumb/title evidence is retained separately
from engine warnings and caption qualifiers. These are evidence candidates,
not verified vehicle matches; dates in copyright/footer text do not establish
model years. A later application must interpret exclusions and contradictions.

`same_text_ids` only identifies repeated searchable wording. `context_alias_ids`
also requires equal title, breadcrumbs, qualifier statements, structure,
figure hashes/captions and reference targets within the same publication.
Every source document retains its own ID and citation. Nothing is merged away.

## References and assets

Relative URLs, percent escapes, Windows separators and fragments are handled
locally. Encoded exporter anchor names retain their exact target spelling.
Reference states are resolved, missing, outside selection, intentionally
unavailable, blocked, or unsupported. External/active URLs, absolute paths,
root escapes and query-dependent endpoints are blocked and never fetched.

To distinguish an excluded target from a missing one, optionally pass
`--source-inventory /path/to/full-extraction/.sme-source-inventory.json` from an
all-publication extraction of the **same source**. Its source identity and
selected file hashes must match. Without that evidence an absent target is
reported as absent from the verified selection; the reader does not guess.

Captions preceding `.imageHolder` images and standard figure captions are
attached to their corresponding images. All original asset hashes remain.
PNG/JPEG/GIF signatures are checked; this is format recognition, not a full
image-decoder audit. Unsupported and missing assets retain explicit reasons.

SVG originals are never approved directly for rendering. A strict static
allowlist emits a separate hash-identified derivative with geometry, text,
ordinary presentation attributes and internal paint references. Scripts,
event handlers, external resources, foreign objects, DTD/entities, unsupported
styles/elements and invalid paint targets are rejected. Metadata and `data-*`
attributes are removed. Only UTF-8 SVG is supported, bounded to 16 MiB,
100,000 nodes and 100 levels. Consumers should render approved derivatives as
images with a restrictive resource policy; unsupported originals remain files
for explicit inspection. No arbitrary source script is part of the content tree.

## PDF pages and OCR

PDF normalization requires Poppler `pdfinfo` and `pdftotext` on PATH. HTML and
Ford extraction do not acquire a Python package dependency. The reader checks
page count, preserves form-feed page boundaries (including blank pages), uses
layout-preserving text, and retains nonfatal Poppler warnings as review metadata.
Unreadable/count-mismatched publications become explicit processing failures.

Each page has one manifest document. Its logical record path is
`.sme-derived/pages/<publication-ID>/<six-digit-page>`; **this is an ID namespace,
not a file to open**. Its citation and PDF-page asset point to the original PDF
and one-based page. Its content hash is the original PDF hash; its text hash is
specific to the page. The original PDF remains the layout/diagram/table reader.
PDF table inference, separate embedded-image extraction and OCR generation are
not performed here. The complete original page is retained as the page asset.

Titles/kinds are conservative hints from first-page text. The owner-manual and
generic-code samples are classified from their text, not their filenames.
Unrecognized kinds remain `unknown`. Full page text and literal applicability
evidence remain available for later review.

Existing OCR output is optional, via `service-manual-ocr-map/v1`:

```json
{
  "contract": "service-manual-ocr-map/v1",
  "entries": [{
    "source_path": "articles/brakes.pdf",
    "source_sha256": "<original SHA-256>",
    "derived_path": "/local/path/searchable.pdf",
    "derived_sha256": "<searchable PDF SHA-256>",
    "page_count": 3,
    "tool": {"name": "OCRmyPDF", "version": "<actual version>"}
  }]
}
```

Hashes and page count must match before OCR is accepted. A relative derived
path is relative to the mapping file. Original page text takes precedence;
OCR supplies only pages with no original text. Each OCR record names the tool
and original hash; its content record also retains the derived-PDF hash.
Page-count/hash matching binds provenance but cannot prove semantic OCR accuracy
or correct page ordering in an incorrectly authored mapping. Mapping producers
must verify page correspondence. Blank pages without OCR remain cited and are
explicitly unsearchable.

## Acceptance on 2026-09-23

- 128 synthetic/regression tests cover the old Ford interface, source reader,
  HTML hierarchy/tables/aliases, link states, active SVG, page boundaries,
  mixed native/OCR provenance, hash changes, partial inputs and atomic output.
- The isolated development environment additionally has `jsonschema`; CI adds
  a Linux Poppler/schema job. Runtime HTML/Ford code remains dependency-free.
- All 113 preserved seller PDFs still match their prior hashes. Normalization
  produced 12,324 cited, searchable pages: 7,606 native and 4,718 OCR, with zero
  document failures. Both content schema and semantic validation pass.
- Eleven hash-checked pages from the partial 6.6L HTML source retained navigation,
  the parent DTC, mismatch warnings, table variants and six CNG diagram captions.
  One real SVG passed the static policy and was visually checked as an offline
  rendered image. The known 760 unreadable source files remain unresolved.
- Original cabin-filter page 1 and 4.3L engine page 17 were rendered and compared
  with their extracted text/citations. The cabin-filter exclusions were retained.
- Browser policy blocked the local HTML preview. Full HTML browser/visual
  acceptance remains open, as does complete-source acceptance for the damaged
  HTML manuals. Structural checks are not a substitute for that remaining gate.

Detailed results and derived packages stay outside Git under
`/Users/asokmathews/Documents/service-manual-data/gm-seller-download-2026-09-17/step4-acceptance/`.
No manuals, PDFs or page text are committed. Step 5 application integration
has not started.
