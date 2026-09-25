# Shared offline viewer v1

Status: Step 7 implemented on `codex/gm-html-manuals`.

The repository now builds the same static viewer shell from either the existing
Ford disc builder or a normalized manufacturer-neutral package. Neutral inputs
do not pass through Ford `.EPL`, SERVICE, EVTM or PCED parsing.

## Build a neutral package

Start with a Step 4 normalized directory containing `.sme-manifest.json`,
`.sme-content.json`, the verified originals and any safe derived diagrams:

```sh
python3 -m sme build-viewer /path/to/normalized -o /path/to/fresh-site
python3 -m fsd serve /path/to/fresh-site
```

`--title` overrides the generic library title. `--json` prints a stable result
summary. The output path must be fresh, outside the normalized input.

## Behavior

- Every selected publication is shown independently; duplicate filenames or
  publication kinds do not replace one another.
- Navigation comes from normalized source routes and breadcrumbs. PDF
  publications receive page-range navigation.
- Search spans all selected publications and can be narrowed to one manual.
- Search results preserve a return link when the user opens a page.
- Resolved references use viewer routes and generate reverse-reference lists.
- Safe SVG and validated raster diagrams are copied by hash and retain their
  captions. Missing, blocked and unsupported diagrams are labeled explicitly.
- PDF results link to the exact page of a locally copied original PDF.
- Native, OCR and unavailable text states remain visible.
- Source HTML and scripts are never copied into executable viewer pages. The
  site contains only the shared application, generated safe fragments, local
  data, verified diagram derivatives and cited PDFs.
- The viewer makes no network requests and retains keyboard search, responsive
  navigation and narrow-screen layouts.

The existing `python3 -m fsd build` and `fsd all` commands remain compatible.
Their Ford-specific parsing produces the legacy data files, while both build
paths copy the same generalized viewer assets.

## Failure boundaries

The builder revalidates the manifest and normalized content before writing. It
hash-verifies every copied diagram and PDF and publishes atomically. A changed
input, existing destination, symbolic link or output nested inside the source
is rejected.

A content package with normalization failures can still be viewed, but the
library and affected pages display the partial state. Building a viewer does
not upgrade incomplete source material to complete or diagnosis-ready status.

## Verification

Committed tests construct two differently titled HTML publications, normalize
them, and verify multiple-book navigation, cross-publication search records,
resolved links, backlinks, local diagrams, missing-diagram labels, search
return state, keyboard support, narrow-screen CSS, fresh-output safety and the
neutral CLI. The full suite also retains all existing Ford, source-reader,
contract and normalization regressions.

Local acceptance on 2026-09-25 built the viewer from the reviewed GM package:
113 publications, 12,324 documents/searchable pages, complete content status
and zero reported failures. Browser checks covered the library, search,
publication/page navigation, return-to-search state, an exact local PDF page
link and the phone-width drawer. A generated-site audit found no missing local
targets, copied-file hash mismatches, external fragment links or remote runtime
assets. Original manual files and generated sites remain outside Git.
