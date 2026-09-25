# GM source support — test and acceptance plan

Date: 2026-09-25
Status: Steps 2–8 implemented. The damaged HTML originals still prevent a
complete-source claim; the verified PDF set and synthetic HTML inputs cover the
implemented application and viewer gates.

## Two levels of evidence

1. Committed synthetic tests: small authored HTML/SVG, generated PDFs and
   generated ZIPs. They
   run without the USB, proprietary content, credentials or a network.
2. Local acceptance: original ZIP checksums, per-member integrity, extracted
   paths/hashes, link audit, source comparisons and browser tasks. Store inputs,
   outputs and detailed logs outside Git; commit only metadata summaries.

## Gates by implementation step

| Step | Cases | Required result |
| --- | --- | --- |
| 1: source integrity | Copy byte/hash match; every ZIP member's size and CRC; PDF folder-vs-ZIP parity, PDF hash/page count, corrupt directory, damaged header/data, missing pages, re-copy/recovery provenance | Distinguish valid source, mismatched copy, damaged source and partial recovery; original hashes remain unchanged |
| 2: contracts | Ford v1/v2 synthetic samples, HTML and PDF collection samples, duplicate archive codes and exact selection; old CLI JSON/exit behavior; neutral schema/version, IDs, unsupported format | Existing consumers remain compatible; unknown format cannot masquerade as Ford, a complete HTML export or a complete PDF collection |
| 3: archive safety | Parent traversal, absolute/drive/UNC paths, separators, control characters, symlinks, nested output symlink, case/Unicode collisions, duplicate members, encryption, truncation, zip resource limits | Reject or explicitly quarantine before publication; no writes outside the selected fresh staging directory |
| 3: repeatability | Nested duplicate basenames; empty files/dirs and OS metadata policy; same-sized changed file; interrupted extraction; re-run; ZIP vs folder | Preserve content paths; validate hashes; publish atomically; report counts/failures consistently |
| 4: HTML roles | Root/index copies, large trees, folder anchors without href, missing body/encoding, empty headings, leaf pages, aliases | Search procedures without shell/navigation pollution; retain hierarchy and all original citation paths |
| 4: context-aware aliases | Identical procedure text but different vehicle, engine, caption or table qualifiers | Preserve separate applicability context and source citations; deduplication cannot broaden a claim |
| 4: relationships | Relative/escaped URLs, Windows separators, anchors, cross-document references, root escapes, absent about page, excluded other-car target | Resolve valid links and classify unavailable ones; never invent a target or fetch source API endpoints |
| 4: content fidelity | Step/Action/Values/Yes/No tables, merged cells, warnings, prerequisite text, parent DTC, variant/caption qualifiers | Context survives normalization and evidence packing without confusing table branches or variant scope |
| 4: diagrams | Preceding captions, multiple figures, PNG/JPEG/GIF/SVG, script/external-link SVG, missing asset, changed hash | Correct caption/asset pairing, explicit supported/unsupported state, checked safe rendering, no source script execution |
| 4: PDF pages | Native-text pages, image-only pages, OCR-derived text, unreadable page, title-page evidence, duplicate filename with distinct hashes, page asset and page citation | Search and citations retain file/page identity and native/OCR provenance; OCR never overwrites or relabels the original |
| 5: application | Probe → choose publication → extract → normalize → search → citation → reader → diagram → return | Shared Ford/GM routes and interactions; IDs scoped to source; results belong to selected manuals |
| 5: failure history | Invalid/partial manifest, failed transaction, reindex after changed source, stale citation, old Ford settings/records | Previous searchable generation survives failure; stale evidence is detectable; historical provenance is retained |
| 5: partial sources | Readable HTML with missing images; missing HTML including navigation; explicitly permitted incomplete browsing | Distinct visible incomplete status and failure reasons; no complete-coverage claim or unqualified diagnostic use |
| 6: applicability | 2001–2005 vs 2006, engine/fuel/cab/transmission/drivetrain unknowns, page disagrees with book, source-claimed equivalents | No silent universal applicability; mismatches visible/excluded as appropriate; qualifiers retained |
| 7: static viewer | Both brands, multiple books, nested pages, search, backlinks, diagrams, keyboard/narrow screen, offline requests | Same viewer interactions; no Ford-only parser dependency for GM; all required assets local |
| 8: checkpoint | Full regression gates, clean content boundary, dependency pin, setup from fresh clone | Reproducible build/tests; no manuals, ZIPs, local indexes, credentials or large derived outputs committed |

Step 2 passed on 2026-09-21: 75 synthetic/regression tests cover the committed
contract, authored HTML/SVG/raster examples, generated PDF pages, Ford v1/v2
records, qualifiers, citations, missing content, native/OCR provenance,
unsupported formats and frozen Ford CLI behavior.

Step 3 passed on 2026-09-22: 100 total tests cover ZIP/folder equivalence,
original path preservation, empty files/directories, same-sized changes,
interrupt/re-run behavior, exact selection, unsafe paths, symlinks,
case/Unicode collisions, duplicates, encryption, corruption and resource limits.
Local read-only acceptance found 113 PDFs/12,324 pages with no failures in both
seller forms and reproduced 760/5,483 failures in the damaged 6.6L/8.1L ZIPs.
Step 4 implementation passed 128 tests (including the optional Poppler/schema
checks in the isolated development environment). The full PDF set produced
12,324 searchable, original-page-cited records with zero processing failures;
all 113 original hashes remain unchanged. Eleven verified surviving HTML samples
and one offline-rendered sanitized SVG were checked. Browser policy blocked the
HTML preview; that visual acceptance gate and the damaged-source gate remain
open. See [CONTENT_NORMALIZATION_V1.md](CONTENT_NORMALIZATION_V1.md).
Step 5 and Step 6 passed in Repair Buddy on 2026-09-23. Step 7 passed on
2026-09-25: 134 extractor tests passed with one optional schema test skipped.
The new shared-viewer tests cover differently titled Ford and Chevrolet
publications, multiple-publication selection, nested navigation, search,
resolved links/backlinks, safe and unavailable diagrams, return state, keyboard
use, narrow-screen CSS, offline-only assets, atomic output and the neutral CLI.
The existing Ford regression suite continues to exercise the same viewer assets.
The reviewed GM package built 113 publications and 12,324 searchable pages;
browser checks covered library/search/page flows and the phone-width drawer.
Every generated PDF/diagram target existed and matched its hash, and no fragment
or runtime asset required a network URL. Step 8 passed on 2026-09-25 in fresh
extractor and Repair Buddy checkouts: 134 extractor tests with the optional
schema test enabled, 234 Repair Buddy tests, Ruff in both, and the documented
tiny HTML input through probe/extract/normalize/build-viewer. A fresh
extractor checkout also built the reviewed 113-publication, 12,324-page GM
package. The Repair Buddy release dependency is locked and independently
checked. See [`STEP8_RELEASE_CHECKPOINT.md`](STEP8_RELEASE_CHECKPOINT.md).

Use tiny constructed adversarial archives; do not actually decompress an
unbounded archive to test resource limits. Generate ZIPs during tests so a
repository-level ZIP exclusion does not require real manual fixtures.

## Initial local known-answer candidates — damaged USB HTML exports

Paths below are relative to the enclosing folder in each 6.6L or 8.1L ZIP.
These are inspected examples, not an approval that they fit either vehicle.
Confirm file integrity before accepting each one into the review set.

| Source path | Expected observation |
| --- | --- |
| `index.html` | Selected 2006 GMC Sierra 2500 HD variant; source-claimed equivalents separate from verified coverage |
| `pages/2.html` | Navigation tree; read failure in the verified source-matching 8.1L copy must be reported |
| `pages/3.html` | Expanded navigation tree; roughly 24,000 anchor elements, including structural anchors without href |
| `pages/100.html` | Labor content explicitly warns of Sierra 1500 4.3 X applicability |
| `pages/1000.html` | Six SVG 6.0L CNG power-distribution figures; should not become diesel/8.1L advice |
| `images/VA229217.svg` | Local vector diagram; validate supported rendering and original identity |
| `pages/1066.html` | Short Circuit Description page needs its parent DTC B1017/B3970 context |
| `pages/2412.html` | Oil-pressure-gauge diagnostic table, including conditional branches and engine-specific values |
| `pages/3738.html`, `pages/6193.html` | Repeated diagnostic material under different navigation paths; retain aliases/citations |
| `pages/10000.html` | Connector pictures and pin/wire/circuit/function table; match captions to all images |
| `external-car.html` | Intentional omitted-content notice, not a procedure |
| `about.html` references | Missing footer target distinguished from a missing diagnostic step |

Once 6.0L integrity is settled, select an equivalent set from that archive and
verify its actual selected year/engine. Do not borrow 6.6L expectations by filename.

## Initial local known-answer candidates — verified seller PDFs

These paths are relative to the seller PDF root. They are local acceptance
candidates only; do not commit the PDFs or claim broader coverage from their
folder labels.

| Source path | Expected observation |
| --- | --- |
| `2006 - 2007/4.3L ENGINE.pdf` | Title evidence identifies a 2006 Chevrolet Silverado 1500; searchable native text and page citation remain tied to the file |
| `2006 - 2007/wiring engine.pdf` | 2006 Silverado 1500 system wiring, 4.3L VIN X; preserve diagram/page context |
| `1998-2007/4.8L, 5.3L, 6.0L ENGINES.pdf` | 2002 Sierra/Silverado engine article, not an all-year fitment claim |
| `1998-2007/6.6L ENGINE.pdf` | 2001–02 6.6L V8 diesel evidence remains separate from gasoline articles |
| `1998-2007/CABIN AIR FILTER.pdf` | Scanned pages become searchable only through derived OCR; source is still the original 2002 article |
| `1998-2007/WIRING DIAGRAMS 1500.pdf` | Scanned 2002 Silverado 1500 wiring material; OCR provenance and page citations are required |
| `2004-Chevrolet-Silverado.pdf` | Owner manual must be labeled as owner information rather than service procedure coverage |
| `GENERIC TROUBLE CODES.pdf` | Generic code list must never be presented as vehicle-specific diagnosis |

## Same-user-task acceptance checklist

Run each action once for a reviewed Ford fixture and once for a reviewed GM
HTML or PDF fixture. Record source revision, expected path, actual result and pass/failure.
Equal page counts or equal wording are not the acceptance criterion.

1. Select a vehicle and inspect available manuals and unconfirmed qualifiers.
2. Search a known DTC and a symptom; see useful section titles and context.
3. Open a result, confirm its citation and complete procedure/table.
4. Follow a reference and return to the same result/query/position.
5. Open a diagram, read its caption, zoom it and return to its procedure.
6. Encounter an inapplicable engine/page and correctly understand the mismatch.
7. Encounter a missing/damaged reference and see what is unavailable.
8. Repeat after reindexing; stale evidence is detected rather than relabeled.
9. Repeat reader navigation using the keyboard and a narrow screen.

## Commands and baseline

Extractor, from `/Users/asokmathews/Documents/ford-service-disc`:

```sh
python3 -m unittest discover -s tests -v
python3 -m fsd --version
python3 -m fsd --help
ruff check .
```

The 2026-09-15 baseline ran **59 tests successfully**, and `fsd --version` and
`--help` succeeded at `f1bdc8d`. Ruff was not run for this documentation-only
change. Existing CI covers Python 3.9/3.13 on Linux, macOS and Windows; retain
that matrix for extraction and synthetic tests.

For Repair Buddy integration, use that repository's configured environment and
its current documented test command. Relevant existing tests cover source
adapters/ingestion, normalization, references, safe HTML, retrieval, pilot
pages and media. Run focused tests while implementing and the full suite before
integration acceptance. Do not claim the old 210-test release result as a fresh
result of this investigation.

Pass reports must include the command, revision, input identity, scope, result
and unresolved issues. A sampled visual inspection cannot substitute for a
complete ZIP integrity scan, and a successful search does not prove diagnosis.
