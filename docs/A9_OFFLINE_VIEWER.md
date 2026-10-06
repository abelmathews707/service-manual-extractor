# A9 — vehicle-scoped offline manual viewer

Updated: 2026-09-27. Branch: `codex/offline-viewer-parity-a9`.

## Result

`python3 -m sme build-library-viewer LIBRARY --review-overlay CURRENT_REVIEW.json -o FRESH_SITE`
builds a self-contained, read-only site from a published multi-manual library.
The trusted current review file must be outside the immutable generation and
must match its recorded revision. The builder verifies packages, search shards,
scope membership and revision identities before publishing a fresh site. It
does not alter the library, the original manuals, Repair Buddy, or the legacy
Ford viewer. GM HTML and PDFs remain on the neutral path, never the Ford `.EPL`
parser.

The site offers cascading make/model/year/engine filters, optional drivetrain
and transmission qualifiers, confirmed/include-possible modes, an explicit
Browse all switch, reference-material switch, coverage and no-content states.
Search fetches only the text shards listed for the selected scope, calculates
ranking within that scope, and cancels prior requests when filters change.
Direct section routes are gated by the same eligibility list. Results show
match state and reason; the site labels its library/review revisions and build
time and explains that newer review decisions require a rebuild. Reviews are
changed in Repair Buddy, not the static site.

Each publication has separate navigation, with duplicate section titles
disambiguated by citation. Section links preserve the selected vehicle, mode,
query and return position. Sanitized local diagrams, captions, tables and exact
local PDF page links are retained. A PDF's other pages are explicitly noted as
not vehicle-filtered. Existing Ford-only and neutral single-package viewers
remain available and now warn that they lack reviewed vehicle filtering.

## Verification

- 181 extractor tests passed; three opt-in tests skipped. Ruff and
  `git diff --check` passed.
- Synthetic Ford, GM HTML, GM PDF and Ford owner-PDF fixtures produced a site
  with the same eligible IDs and states as the published search export. A
  review acceptance changed the intended membership only after republishing
  and rebuilding; a stale review, changed shard, or review inside the immutable
  generation was refused.
- A disposable local five-publication build produced 267 searchable sections.
  In a browser, 2003 Ford F-250 6.0L diesel confirmed search returned four
  Ford sections; the local server recorded one Ford-only shard request and no
  GM text-shard request. GM HTML showed all four distinct links, including two
  same-named sections. The GM PDF opened its original at `#page=1` and showed
  the searchable excerpt. Phone-width (390 px) layout, menu, keyboard shortcut,
  search-to-section return and local assets were inspected.
- The generated shell references local CSS/JS/data only. The browser test used
  a loopback HTTP server; a literal browser-offline/network-disabled mode was
  not available in that test environment. This narrower evidence must not be
  described as an air-gapped browser test.

The disposable acceptance inputs and generated sites are outside Git under
`/private/tmp/repair-buddy-a8-check.v5BEYA/`; they are fixtures, not a complete
inventory of the owned manuals. No live database or original manual was changed.

## Remaining limits and next step

The site is a versioned snapshot: it cannot see decisions made after its build.
The filtered HTML/PDF examples passed, but real-library reconciliation,
sampled source-page inspection, performance targets and a complete offline
browser acceptance remain for A10. Unknown coverage is not complete coverage.

A10 should inventory every supported manual in hand, convert/import or record
an exact pending reason, build a combined library and disposable Repair Buddy
database, then compare both readers against reviewed Ford and GM positive and
negative examples. Check original/derived hashes and sample pages, diagrams,
tables and OCR. Measure cold build and warm scoped-search latency, cancellation,
memory and disk use. Preserve a recoverable backup before any normal-use
promotion, publish a reproducible acceptance report, and stop before Phase B.
Pass when no supported item is silently lost, no wrong-vehicle text leaks,
citations/coverage agree between readers, and all local regression checks pass.
Recommended model: GPT-6 Sol / High.
