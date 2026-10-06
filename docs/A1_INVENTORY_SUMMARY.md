# A1 — inventory and acceptance sample reconciliation

Status: complete on 2026-09-25. This records existing inventory evidence and
targeted citation examples. No manuals were re-extracted, OCRed or imported.

## Current library states

| Material | Cataloged/source count | Indexed/processed state | Vehicle mapping state |
| --- | --- | --- | --- |
| Ford service-disc media | 4 source folders; 64 archive occurrences; 44 unique archive hashes; 41 unique English publications extracted | Repair Buddy has 33 indexed + 8 indexed-partial publications, 18,292 documents and 64,906 fragments; 23 entries are catalog-only | 484 applicability rows all omit make, engine, transmission and drivetrain. Catalog names include Ford, Lincoln and Mercury vehicles. |
| Ford owner guide PDF | One separate legacy PDF | 280 pages; all 280 contain text; tracked through the older manuals/pages tables | Owner material; not in the 18,292 document count. |
| GM PDF set | 113 publications / 12,324 original pages | All 113 are normalized and in the local offline viewer. The disposable Repair Buddy acceptance DB indexed 3 publications / 107 pages and cataloged 110 without documents. Ordinary local Repair Buddy remains Ford-only. | Seller folder names and broad article titles do not prove exact vehicle coverage. |
| GM HTML replacement | User reports replacement files obtained | No replacement HTML path or fingerprint found in the known local paths. The Silverado/Sierra folder below contains PDFs only. | Pending source identity and integrity record. The earlier USB damage is historical, not a project blocker. |

The GM PDF set contains 7,606 native-text pages and 4,718 OCR-derived pages.
The seller's extracted Silverado/Sierra folder is now stored at
`/Users/asokmathews/Documents/service-manual-data/gm-seller-download-2026-09-17/from-downloads/Chevrolet Silverado GMC sierra 1998-2007`.
It contains 113 PDFs, no HTML/HTM, and was verified with `diff -qr` to match
the preserved `from-archive` folder exactly. The preserved source ZIP has
SHA-256 `52ccd0e43acef9f71dd05befdce5d5d20a61e02f172300b6f42ca8c8c8d79816`.
This is the known PDF package, not the replacement HTML. Its normalized source
ID is `src_241ae321543b966629942d2b1977d6eb`.

## Acceptance examples selected

Detailed local citation locators and expected outcomes are in
/Users/asokmathews/Documents/service-manual-data/a1-inventory-2026-09-25/acceptance-cases.md.
They cover:

- 2003 Ford F-250 6.0L diesel, with the partial 6.0L PC/ED publication and
  unsupported F-450/F-550/Excursion inheritance kept visible.
- Ford-produced media that names Lincoln or Mercury models.
- 2006 Chevrolet Silverado 1500 4.3L VIN X native wiring and an adjacent PDF
  page that transitions from a 4.3L figure to a 4.8L section.
- A page-level GM cabin-filter exclusion, the article's year limit, and
  explicit Sierra/Silverado shared article scope from OCR text.
- A generic OBD-II reference that cannot claim a vehicle-specific repair fit.
- Same-displacement Ford and GM engines, for which displacement alone cannot
  establish engine identity.

Tests for exact but unavailable variants will use synthetic fixtures. Direct
OCR evidence remains subject to original-page review. The replacement HTML is
not part of this sample set because its local path has not been identified;
the moved GM PDF folder was checked and contains no HTML/HTM files.

## Performance/software baseline

Read-only full-text searches against the 18,292-document Ford DB returned 318
matches for starter AND relay, 359 for fuse AND panel, and 79 for C500.
The three SQLite FTS queries took 0.01 seconds total in one local command on
this machine. This is only a raw unscoped database timing; the current app has
no vehicle-specific pre-search scope and no instrumented scoped-search timing.
Step A6/A7 should compare the real end-to-end scoped workflow against this
baseline and instrument which eligible IDs were searched.

Recorded environment: macOS 14.4.1, arm64, system Python 3.9.6, SQLite 3.43.2,
Git 2.39.3. Dependency revisions at audit time:

- extractor planning branch: ea029252182c35637f515271a2dc398f535238fd
- Repair Buddy merged remote main: 310ce810f9129576d5f0f72b37a27f35cac699a8
- workshop-manual-toolkit main: d150e7d889eb55ebba85065da264ab2bc414755d

## Evidence limits and next work

The Ford and GM totals refer to different stages and databases; they are not
one imported combined library. The old 484 structured Ford rows cannot prove
make/engine coverage because those columns are empty. The GM application test
database is disposable, and only 3 of 113 normalized publications were indexed
there. Product-level scoped search performance remains unmeasured until A7.

The replacement HTML path is pending; continue contract and bridge design
without repeating USB recovery. A2 is next: freeze versioned vehicle,
applicability, review and scope contracts with truth tables before implementation
of the matcher. Recommended model: GPT-6 Sol / High.
