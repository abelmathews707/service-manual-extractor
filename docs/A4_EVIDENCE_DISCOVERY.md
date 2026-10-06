# A4 — source discovery and applicability evidence

Status: complete on 2026-09-26 on `codex/applicability-evidence-a4`.

## Delivered

- `sme discover FOLDER` inventories immediate children and reports recognized,
  partial, failed and unsupported inputs. Ford disc trees/images route to the
  Ford adapter; ordinary HTML/PDF folders, ZIPs and PDFs route to the neutral
  importer. A GM input is never parsed as a Ford `.EPL` file.
- `sme process-folder FOLDER -o CACHE` builds version-keyed neutral packages.
  Exact Ford archive identities can be selected; mixed Ford POD generations
  become separate packages. Repeated runs verify original hashes and reuse
  intact results. Changed source or transformation bytes create a different
  cache key rather than replacing a prior package.
- `sme emit-evidence PACKAGE VOCABULARY -o FILE` emits the A2
  `applicability-evidence/v1` contract: source-bound units, assertions, original
  citations, include/exclude wording, text provenance and conservative
  correlated vehicle alternatives. Ford `.EPL` fields and original wiring SVG
  `<desc>` qualifiers are cited to their original members. Publication titles,
  folder names and OCR text do not silently become confirmed whole-book fit.
  Mixed-engine pages remain metadata-only for scoped text search.
- `sme plan-ocr PACKAGE` uses text and raster-image presence per original PDF
  page. Image-only pages are automatic candidates; low-text pages, including
  diagrams with a native footer, require review. `sme toolkit-ocr` invokes
  the independently versioned workshop toolkit's page extraction and merge
  helpers for selected pages, keeps the original PDF, and records a hash-bound
  OCR map, tool/script version, page correspondence and warnings. It does not
  alter the toolkit repository.

## Verification

- Full extractor suite: 165 tests passed; one opt-in real-OCR test skipped in
  the default run. That test separately passed twice with the installed
  toolkit, including re-normalization with the resulting OCR map and cache
  reuse. Ruff and `git diff --check` passed.
- Authored Ford POD v1/v2, HTML and PDF fixtures exercise the common evidence
  contract, original citations, misleading years, title hints, exclusions,
  mixed-engine material, aliases and invalid vehicle combinations.
- Real Ford incoming folder: four disc directories recognized, 64 archive
  occurrences listed, one `.DS_Store` unsupported. A selected 2012–13 PC/ED
  archive built one package with no failures; a repeat verified and reused it.
- Real seller GM normalized PDF package: 12,324 units and 53,876 cited
  assertions across 113 PDFs. PDF page triage counted 7,597 native-readable,
  4,718 already OCR, eight low-text-with-image review pages and one other
  low-text review page. Those nine pages were **flagged**, not silently OCRed.
- Representative real Ford workshop evidence produced 4,068 units and 6,852
  assertions. A regenerated wiring book produced 776 units and 826 assertions,
  including 433 statements cited to original SVGs (45 qualifiers). These
  totals are evidence candidates, not verified vehicle coverage counts.

## Limits and deferred input

- The replacement GM HTML path has not been identified. The earlier damaged
  USB copies are historical and are not used to claim accepted HTML coverage.
  When the replacement path is supplied, validate it independently through
  discovery, source integrity and evidence capture.
- OCR output is derived text, never a correction to source truth. Review any
  OCR qualifier before approving applicability. A short native footer may
  still coexist with a scanned diagram; the nine flagged GM pages need review.
- A4 records evidence and proposals, not final search eligibility. A5 must
  apply the deterministic matcher and human review overlay before a vehicle
  claim can be treated as confirmed. The current Repair Buddy database and
  workshop toolkit checkout were not modified.

## Next step

A5 implements the A2 truth tables as a pure matcher over source evidence,
canonical vehicle scope and an append-only review overlay. It must preserve
exclusion precedence and child restrictions, surface conflicts and missing
qualifiers, propose only bounded shared-content relationships, and make stale
or revoked approvals ineligible after reimport. Pass: all truth tables and
review lifecycle tests pass; similarity alone never confirms fitment.
Recommended model: GPT-6 Sol / High.
