# Step 8 — reviewable release checkpoint

Date: 2026-09-25. Candidate branch: `codex/gm-html-manuals` at
`96b0c47e20f9948c8fa08b8954e08844e399fd6b` before this documentation
commit. No merge, tag, package publication or manual redistribution was made.

## Supported scope

- The existing `fsd` Ford-disc command and its single-book-per-role builder
  remain compatible. `sme` independently probes and extracts supported static
  HTML exports, PDF collections, individual PDFs and ZIP/folder containers.
- `sme normalize` creates cited neutral HTML records or per-page PDF records.
  PDF text may be native or from a separately hash-checked OCR copy.
- `sme build-viewer` makes a fully local shared viewer with multiple
  publications, nested navigation, scoped/library search, return links,
  captions/diagrams, keyboard controls and narrow-screen layout. GM content
  never goes through the Ford `.EPL` parser.
- Repair Buddy's integration branch `codex/gm-applicability-parity` at
  `f062b90ea137b80b66d794ac969d09ac38fc98d0` imports neutral packages
  into its existing source/search/reader flow. Its release lock points to the
  extractor candidate revision above. Each actual import also records its
  extractor revision.

The verified seller PDF collection contains 113 publications and 12,324 pages.
All were normalized and built into an offline viewer: 7,606 native-text pages
and 4,718 OCR-derived pages. This is a patchwork of GM truck/SUV articles,
including 2000–03 material, a 2004 Silverado owner manual and a 2006
Silverado/Sierra article set. Those labels are not a verified model/year/engine
coverage claim. Original 6.6L and 8.1L HTML ZIPs still have 760 unreadable
images and 5,483 unreadable HTML files respectively; the 6.0L original is
structurally corrupt. The surviving HTML samples and synthetic fixtures
validate behavior, not complete source availability.

## Reproduction gate

From a fresh checkout of the candidate branch, use Python 3.9+ and install
`jsonschema` and `ruff` for the full optional-schema test gate. Poppler's
`pdfinfo` and `pdftotext` are required for PDF normalization. No network is
needed to run an already built viewer.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install jsonschema ruff
python -m unittest discover -s tests -v
ruff check .
python -m sme --help
python -m sme probe tests/fixtures/html_manual --json
```

The exact fresh-checkout gate passed on 2026-09-25: 134 extractor tests with
the optional schema test enabled, Ruff, `fsd`/`sme` CLI smoke checks and a
probe → extract → normalize → build-viewer run on the committed tiny HTML
fixture. The reviewed local normalized GM package built a site with all 113
publications and 12,324 searchable documents, zero build failures. The
separate Repair Buddy fresh checkout passed 234 tests and Ruff. Source files,
test databases and generated sites stayed outside both repositories.

## Release boundary and remaining work

Neither repository bundles owned manuals, OCR output, local databases or
generated sites. A user needs their own legitimately held input and must
review applicability and OCR before using results for vehicle-specific work.
The Ford legacy builder still has its historical first-book-per-role limit;
use the neutral viewer for multiple publications. PDF tables remain original
page images, not inferred structured tables. The earlier USB copies were
damaged; the user reports replacements are available, but this checkpoint did
not verify their integrity or complete real-HTML browsing. That is separate
follow-up acceptance, not a blocker to merging this code. Make/model/year/engine pre-search filters and matching modes are
not implemented. AI diagnosis, public distribution and commercial release
planning are separate later work.

Review both branch diffs, the Repair Buddy dependency lock and these limits
before deciding whether to merge or tag. No public release is implied by this
checkpoint.
