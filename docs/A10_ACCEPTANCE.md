# A10 - real-manual engineering acceptance

Date: 2026-09-28. Branch: `codex/real-manual-acceptance-a10` in both
independently versioned repositories. This report supersedes the earlier
pilot/full-v1 checkpoints in [A10_PROGRESS.md](A10_PROGRESS.md).

## Delivery boundary

This is the first combined local manual-library acceptance, not a public
release, complete vehicle-coverage claim, human approval, or live AI diagnosis.
The reviewed mapping vocabulary contains only four configurations: 2003 Ford
F-250 6.0L Power Stroke diesel; 2002 Silverado 1500 4.3L VIN W; and 2006
Silverado 1500 4.3L VIN X / 4.8L VIN V. Processing every available file does
not prove that every vehicle, engine or procedure has been covered.

All original manuals remain read-only and outside Git. The existing live
Repair Buddy database was not imported into or activated with this library.
Only a disposable SQLite backup was changed. The ordinary Repair Buddy
checkout's three user documentation changes and the toolkit's untracked
`-.ppm` were preserved. No merge, tag, release or Phase B work was performed.

## Final library and source accounting

| Input | Publications | Normalized documents/pages | Evidence units |
| --- | ---: | ---: | ---: |
| Ford source A, POD generation 1 | 6 | 5,723 | 12,714 |
| Ford source A, POD generation 2 | 12 | 1,915 | 7,391 |
| Ford source C | 12 | 8,561 | 16,839 |
| Ford source D | 11 | 5,556 | 20,570 |
| Ford 2003 Super Duty owner PDF | 1 | 280 | 280 |
| Seller GM PDFs | 113 | 12,324 | 12,324 |
| Total | 155 | 34,359 | 70,118 |

Documents and evidence units are different measures: an HTML document may
produce a page, table and figure unit. There are **30,854 distinct searchable
units**. The offline viewer additionally retains **3,505 top-level unsearchable
originals**, such as mixed-engine pages and image-only pages. Child metadata
units do not become duplicate page readers. Withheld pages remain absent from
every text-search shard, even in Browse all.

The final immutable export has 52 scopes, 848 text shards and 217,168 eligible
scope rows. Its GM pages remain 7,606 native-text plus 4,718 OCR-derived pages.
The corrected GM evidence has 41,552 assertions; the earlier 53,876 count is
historical and must not be mixed with this generation. The toolkit produced
separate searchable PDF derivatives, not conversions of existing HTML into OCR.

Full reconciliation verified **64,600 original member files** and **43,515
unique derived assets** by their recorded hashes. Asset-reference counts in
individual packages can repeat the same physical file and are not unique-file
counts. Of the old Ford database's 18,292 document records, 16,880 resolve to
the canonical new citation bridge; the other 1,412 are auxiliary XML records
whose originals are retained byte-for-byte. They are not silently converted
into searchable procedures. There are 61 additional PDF page resolutions.
The reconciliation report has zero unexplained missing old citations.

The disposable app retained all 23 pre-library tables row-for-row, comparing
in both directions against the untouched live database. All 280 old owner-guide
page links and its original-PDF route remain usable. SQLite integrity is `ok`.

### Explicit pending and duplicate inventory entries

- Ford source B's 20 archive occurrences are byte-identical to already imported
  archives. They remain preserved/cataloged, not counted as 20 new publications.
- French-Canadian S21 has the known strict decoder failure (chunk 16,388 bytes
  exceeds the 16,384-byte boundary). It remains pending; broad recovery was not
  attempted. French-Canadian V22 remains deliberately outside the selected
  English import. The empty VCQ electric-vehicle referral has no manual pages.
- Source D contains malformed optional `EDO119005.xml`. The reader now records
  `ford_wiring_xml_partial`, retains the original XML and all 397 healthy EDO
  wiring pages, and does not claim that page's metadata is complete.
- Replacement GM HTML files were reported by the user, but their exact local
  path and verified source identity are still unknown. The known moved folder
  contains the 113 PDFs, not HTML. Old damaged USB copies were not substituted
  and their recovery is not a blocker for this delivery.
- Some image-only Ford PDF attachments have no searchable text. Their original
  pages are retained and explicitly labeled, not represented as OCR success.
- Exact Tahoe Classic / Yukon Denali exclusions and Sierra shared applicability
  are visible in the reviewed cabin-filter source, but those configurations are
  not in the pilot vocabulary. Canonical end-to-end validation for those exact
  variants remains pending vocabulary expansion; adversarial synthetic tests
  cover the contract boundaries. No blanket OCR/all-engine approval was made.

## Changes made to pass acceptance

1. PDF titles now use source path/page rather than carrying a first-page engine
   heading onto later pages. Original bytes, OCR linkage and source hashes are
   unchanged. Page-specific evidence is rebuilt against the corrected package.
2. An accepted native-text same/next-page figure caption can supply a missing
   engine qualifier. It cannot override exclusions, mixed content, conflicting
   source support or stale reviews. Six agent-pilot events bind three exact GM
   page/caption examples; they are not human or production review decisions.
3. Optional malformed Ford wiring metadata no longer discards healthy circuit
   sheets; the exact defect is reported instead.
4. Whole-page originals withheld from search are accessible through explicit
   unfiltered browsing in both readers. Normal scoped readers still reject
   those links. The app has a paginated unsearchable-original catalog.
5. Cold exports emit progress and check cancellation during copying, scope
   construction and before activation. Cancellation/interrupt cleans the staged
   build and preserves the previous pointer.
6. Viewer shard downloads are limited to six simultaneous requests, preserving
   order, revision/hash checks and cancellation. An intermittent broad-search
   fetch failure during a rapid year change prompted this hardening; reload
   recovered the earlier build, and the bounded build is the final test target.
7. Portable PDF tests are guarded when optional Poppler is absent, while the
   dedicated PDF/schema CI job still executes them. ZIP safety now checks the
   raw central-directory name before platform separator normalization or NUL
   truncation; Windows safety fixtures preserve the authored raw name.

## Reviewed real examples and reader parity

Reviewer: Codex, agent engineering review, 2026-09-27/28. Original pages were
inspected visually, not approved solely from extracted text. This is a disposable
pilot overlay; owner sign-off remains separate.

| Case | Expected and observed boundary |
| --- | --- |
| Ford 2003 F-250 6.0L diesel, native HTML | 127 confirmed sections; `fuel` returns 40 results. Diesel Fuel System retains item tables, diagrams and source citation. |
| GM 2002 Silverado 4.3L VIN W | Injector query returns only ENGINE PERFORMANCE page 87, with its native VIN W/X caption and exact original page link. |
| GM 2006 Silverado 4.3L VIN X | Confirmed result is wiring page 2, supported by adjacent caption page 3; VIN V page 10 is not eligible. |
| GM 2006 Silverado 4.8L VIN V | Confirmed result is wiring page 10, supported by caption page 11; VIN X page 2 is not eligible. |
| Mixed wiring page 9 | Excluded from text search and normal engine-scoped readers; readable only as an explicitly unfiltered original, with `mixed_content` warning and page-9 citation. |
| OCR cabin-filter article | Three possible pages for the 2002 selection, `missing_engine`; absent from confirmed-only mode and the 2006 article scope. Other 2006 HVAC pages mentioning cabin may still match. |
| Generic OBD-II reference | Available only after reference opt-in, labeled reference rather than a confirmed vehicle repair fit. |
| Wrong make/engine, stale review, cancellation | No scope widening or wrong-vehicle direct-reader access; stale snapshots fail; cancelled work cannot replace the current result/generation. |

Automated disposable parity compares all 52 scopes and all 217,168 eligible
rows, including IDs, statuses/reasons and the four confirmed search result sets.
Both readers retain original PDF links and warn that a whole PDF's other pages
are not vehicle-filtered. Browser checks cover filters, results, native tables,
diagrams, possible OCR text, original-page anchors, keyboard return and 390-pixel
layouts without horizontal page overflow.

The 390-pixel layout review was performed on full-site-v3 and the app reader;
v4's stylesheet is byte-identical (SHA-256
`f3d72fabffde9763809c6c5ecb3bbab79cf55b9c22793eee52aefae56a1281f7`).
The final v4 browser walkthrough repeated scoped searches, broad year/engine
transitions, reference opt-in and mixed-page reading. A repeat viewport override
did not apply to the current browser surface (it stayed 1280 pixels); no new
390-pixel v4 screenshot is claimed. The v4 change affects request scheduling,
not the previously reviewed layout.

The offline harness serves unchanged generated files on loopback HTTP, blocks
remote subresources with a self-only Content Security Policy and rejects/logs
remote fetch attempts. This is an enforced browser offline policy, not a claim
that macOS Wi-Fi was turned off. Before any GM selection, the Ford fuel query
requested exactly five shards, all verified as Ford `useni4/v3d` text, and no
GM-only shards. No remote fetch attempts were recorded. Initial metadata still
describes the whole library; the claim is about text loading/search, not hiding
all GM catalog metadata.

## Performance, storage and limitations

Machine: macOS 14.4.1, arm64, 8 GB RAM; system Python 3.9.6. Measurements use
30 warm repetitions per scope. They measure search-engine time, **not** browser
click-to-paint p95 or initial index download/render time.

| Scope | Export search p95 | App database search p95 |
| --- | ---: | ---: |
| Ford confirmed (127 units) | 0.026 s | 0.021 s |
| Ford including possible (6,837 units) | 1.009 s | 0.811 s |
| GM 2002 including possible (3,296 units) | 0.387 s | 0.293 s |
| GM 2006 including possible (4,817 units) | 0.338-0.386 s | 0.270-0.274 s |
| Browse all (30,854 units) | 5.563 s | Not measured |

Confirmed GM scopes contain only one reviewed page each; their sub-millisecond
backend times are not representative of broad GM searching. `fuel` correctly
has no hits on the two confirmed wiring pages; the reviewed known-answer query
uses page text that is actually present.

The cold combined export took 362.843 seconds with visible progress. Search
cancellation between shards took 0.0093 seconds. The measured process maximum
RSS was 1,505,542,144 bytes; this includes Python index/measurement allocations
and is not isolated browser memory. The immutable generation occupies
3,428,785,681 bytes and the search index 58,695,008 bytes. The disposable DB is
about 1.2 GB. Broad possible queries load more text (Ford about 19.9 MB); Browse
all loads about 90.5 MB. Browser request concurrency is bounded, but ranking
and complete initial metadata still need optimization for larger libraries.

ScopeCache has a default 16-entry LRU (configurable bound 1-128). Per-query
text/token arrays are not a persistent full-library text cache. Local HTTP
browser caching depends on server headers; the acceptance harness uses no-store.
Historical builds are retained locally and increase disk usage beyond the
single-generation figure. No originals or old output were deleted.

**Documented performance exception:** Ford possible-mode export p95 exceeds the
provisional one-second target by 0.009 seconds; Browse all is substantially slower.
Browser latency/memory are not fully instrumented. These are not hidden passes:
the local engineering checkpoint is bounded, and public/user-facing performance
release readiness is not claimed. Benchmark concurrent acceptance activity may
affect results; retain the measured values rather than replacing them with the
earlier faster three-sample run.

## Regression and CI gates

- Fresh pinned Python 3.14 environment, with schema/PyMuPDF and real toolkit
  OCR enabled plus bundled Node on PATH: **190 tests pass with no skips**.
  Ruff and JavaScript syntax checks pass. Minimal system Python 3.9 tests also
  pass, with optional dependency tests skipped when unavailable.
- Fresh pinned Repair Buddy Python 3.14 environment: **266 tests pass**; Ruff
  and diff whitespace checks pass. No application CI workflow exists in this
  repository; the fresh local suite is its integration gate.
- Extractor final runtime CI: [run 36386685118](https://github.com/abelmathews707/service-manual-extractor/actions/runs/36386685118),
  all nine jobs pass: Windows/macOS/Linux on Python 3.9 and 3.13, dedicated
  PDF/schema, lint and no-manual-content checks. Earlier CI failures exposed
  missing optional-Poppler guards, raw ZIP-name platform differences and a
  Windows fixture encoding; those were corrected, not hidden by skipping
  archive-safety or JavaScript scheduler tests.
- Existing SWIG/PyMuPDF deprecation warnings do not fail tests; toolkit internals
  were not changed to silence them.

## Revisions and reproducible local records

- Extractor tested runtime code baseline:
  `8c14fc2e3e0f2668f50587c9f0b3ecfc151102fb`, pushed on the A10 branch.
  Repair Buddy's `config/service-manual-extractor.lock.json` records the exact
  dependency snapshot, including any following documentation-only checkpoint.
  Search transform remains
  `edf306508dba82a8cc55a43acf9c195f623533b6973060f085083d025d4add84`.
- Library revision:
  `bd9bd781c2dbe3054b7311d3d5fead8015b0cf977e026f7ac953c7447a750bf3`.
- Review revision:
  `1d4c41c25d2932329ce183c9394250dbe828565390854a00abce3eeceb85c17f`.
- Immutable generation:
  `d68c771ea3fea5b12d0e84fe9b2585abf56fbdff62a4d8fcc357271146e00ec2`.
- Library manifest SHA-256:
  `d0f40d9b8d659fbefb32e6847c06aca45bf63bda97374ea2cb1e8f54e9182477`.
- Independent toolkit:
  `d150e7d889eb55ebba85065da264ab2bc414755d`, unchanged on `main`.

All detailed inputs/results stay under
`/Users/asokmathews/Documents/service-manual-data/a10-acceptance-2026-09-27/`:
`full-library-v2`, `full-review-v2.json`, `full-site-v4`,
`repair-buddy-full-disposable-v2.sqlite3`, `full-reconciliation-v3.json`,
`full-measure-v2.json`, `full-app-parity-v4.json` (30-sample app timings), and
`full-app-parity-v7.json`. Older v1/v2/v3 site/pilot outputs are
historical and are not the final viewer.

Reproduce with the acceptance scripts in this repo and the app's
`scripts/a10_verify_disposable.py`. Optional dependency pins are in
`acceptance/requirements-a10.txt` and app `scripts/requirements-a10.txt`.
Use fresh environments and both repositories on PYTHONPATH for cross-repo
checks. Supply the current overlay outside the immutable generation. Use only
the disposable database, never the live path, for imports. The normal extractor
runtime remains dependency-free; manual bytes are not committed.

## Next step after acceptance: B1, only when selected

Phase A delivers readable/searchable source evidence with conservative vehicle
matching. Phase B makes selected content machine-structured for later hybrid
retrieval and reasoning. It does not replace original manual reading or relax
eligibility, citation, review and staleness checks.

B1 defines separate typed schemas for procedure steps, specifications, part
references, diagnostic graph nodes/branches, tools, warnings/prerequisites and
diagram/table regions. Each keeps exact source wording and locator, source/text
hashes, original and normalized values/units/conditions, applicability,
extraction version and review state. Missing values are not zero; a mentioned
part is not approved fitment or supersession.

Select a small independently reviewed benchmark spanning Ford tables, native
HTML, native PDFs and OCR PDFs, plus ambiguous/unreadable cases whose correct
answer is abstention. Keep a held-out subset and define field-level accuracy,
abstention and complete diagnostic-branch gates before scaling extraction.

Pass criteria: each type validates, opens the exact original source, has
positive/negative/abstention examples and explicit quality thresholds; Phase A
reader/search boundaries do not regress. B1 is not bulk extraction or a paid
AI runtime integration. Recommended development model: **GPT-6 Sol / High**,
as already recorded in the plan. This is engineering judgment, not a guarantee
or measured model comparison; official documentation describes Sol as suited
to complex coding and supports High reasoning:
[GPT-6 Sol](https://developers.openai.com/api/docs/models/gpt-6-sol).

Do not start B1 on this acceptance continuation. Separately selecting promotion
requires a recoverable backup, explicit target DB/config, revalidation of review
authority and a rollback check; acceptance did not authorize live activation.
