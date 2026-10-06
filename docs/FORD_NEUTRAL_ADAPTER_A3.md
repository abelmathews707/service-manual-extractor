# Ford archive → neutral manual package (A3)

Status: implemented and locally validated, 2026-09-26.

The new `sme ford-probe` and `sme ford-import` commands wrap the existing `fsd`
archive readers. They do not replace or change the legacy `fsd` command. GM
HTML/PDF reading stays in the neutral adapters and never invokes Ford EPL
parsing. The package still uses `service-manual-manifest/v1`,
`service-manual-content/v1`, and `service-manual-source-inventory/v1`, so the
shared offline viewer reads it without a Ford-only path.

## Selection and identity

`ford-probe <disc-folder-or-image>` lists exact, source-relative archive
identities and POD generations. Select one or more of those identities:

```text
python3 -m sme ford-import DISC -o NEW_PACKAGE \
  --archive content/useni4/s3o.arc
python3 -m sme build-viewer NEW_PACKAGE -o NEW_VIEWER
```

The destination must not already exist and cannot be inside the source.
Extraction is staged, validates archive decompression and hashes the selected
archive before and after reading, then atomically publishes the package. The
originals remain untouched. Ford discs sometimes mix POD v1 and v2; import
each generation into its own package. A6 will assemble several packages into
one vehicle library. Display codes are never selectors, and two same-code or
same-role books remain separate publications.

The source ID records the selected archive identities, byte hashes, POD
generation and container. Each archive occurrence gets a distinct publication
ID. Every original extracted file remains under `originals/` in the package.
The `.sme-ford-identity.json` bridge maps the old Repair Buddy book key,
filename, optional anchor or PDF page, and old viewer route to the new
publication/document IDs. `resolve_legacy_citation()` rejects absent or
ambiguous references instead of choosing a same-code book arbitrarily.

## Content and capability boundaries

- Workshop and PC/ED HTML retain procedure text, safe structure, local links,
  return links, figure captions, Ford navigation routes, original paths and
  anchors. Ford's CP1252 fallback applies only in this adapter.
- Printable PDFs retain the original bytes and page citations. Native text is
  indexed per page; pages without text remain browsable but unsearchable.
  Ford HTML links to a PDF open its first cited page. Each PDF has its own
  page group in the viewer, so page numbers do not collide.
- Newer wiring XML page records become cited page documents with searchable
  titles, labels and connection names. Associated SVGs become static, locally
  sanitized derivatives while the originals remain untouched. Bounded inline
  PNGs in a Ford SVG are checked as PNG data, not fetched from the network.
- Older wiring MDB databases are preserved but not interpreted. The adapter
  does not claim connector/pin records from them. XML with no recognized Ford
  wiring-page mapping, unsupported figures and failed PDF/HTML reads are
  enumerated in `.sme-ford-capabilities.json` and/or the content failure list.
  These gaps must not be presented as complete diagnostic coverage.

The adapter records raw publication-level vehicle wording from EPL as evidence,
not a confirmed make/model/year/engine match. A4 and A5 turn source statements
into reviewed applicability decisions; A6 scopes the search data before a
query, and A7 connects that to Repair Buddy and its future hybrid RAG. This
step does not activate AI retrieval for newly imported manuals.

## Acceptance evidence

Synthetic tests exercise POD v1/v2, two same-code workshop books, return links,
the old-identity bridge, PDF page links, and mixed-generation rejection. The
full extractor suite passed (154 tests) with `jsonschema` enabled and Ruff
passed. Local owned-media spot checks (kept outside Git):

| Archive | Result |
| --- | --- |
| 2001 `S1O` v1 workshop | 1,626 HTML documents, 1,462 searchable; 26,659 raster figure references; viewer built |
| 2012 `VC2` v2 diagnostics | 234 HTML documents, 217 searchable; viewer built |
| 2012 `ECO` v2 wiring | 388 cited, searchable XML pages with 388 sanitized SVG diagrams; viewer built |
| 2003 `S3O` v2 workshop | 1,753 HTML documents plus 4,814 cited PDF pages; 1,463 HTML-to-PDF links resolved; viewer built |
| 2003 `E3O` v2 wiring | 573 PDF pages preserved; MDB remains explicitly uninterpreted |

These counts describe extracted content, not verified vehicle fitment or
diagnostic accuracy. The complete original collections and large generated
packages are local-only and must never be committed.
