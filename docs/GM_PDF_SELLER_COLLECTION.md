# GM seller PDF collection — inspection record

Date: 2026-09-18
Status: source preserved, archive extracted and validated; no GM importer has
been implemented.

This is a separate input from the damaged GM HTML ZIPs recorded in
[GM_HTML_INSPECTION.md](GM_HTML_INSPECTION.md). It neither repairs nor replaces
those files.

## What arrived

The seller supplied a folder plus an outer ZIP with the same 113 PDFs. They are
GM service articles and reference material, primarily for full-size trucks and
SUVs—not a complete, year-by-year manual library for every GM vehicle.

| Item | Location / identity |
| --- | --- |
| Local data root | `/Users/asokmathews/Documents/service-manual-data/gm-seller-download-2026-09-17` |
| Seller folder | `original/Chevrolet Silverado GMC sierra 1998-2007/` |
| Seller ZIP | `original/Chevrolet Silverado GMC sierra 1998-2007-20260918T000530Z-1-001.zip` |
| Outer ZIP SHA-256 | `52ccd0e43acef9f71dd05befdce5d5d20a61e02f172300b6f42ca8c8c8d79816` |
| Independent extraction | `from-archive/Chevrolet Silverado GMC sierra 1998-2007/` |
| Source files | 113 PDFs; 12,324 pages |

All originals, extraction output, manifests and analysis remain outside Git and
outside Repair Buddy's live database.

## Integrity and readability

| Check | Result |
| --- | --- |
| ZIP member test | 113 members; no compressed-data errors |
| Folder vs extracted ZIP | 113 of 113 match byte-for-byte by SHA-256 |
| Duplicate source PDFs | None by SHA-256 |
| PDF metadata/readability | 113 of 113 readable; none encrypted |
| Text extraction | 113 of 113 commands completed |
| Native-text PDFs | 39 files; 7,606 pages |
| Scanned/image-only PDFs | 74 files; 4,718 pages |
| Title-page OCR | 74 of 74 scanned PDFs rendered and OCR-read successfully |
| Full searchable copies | 74 of 74 scanned PDFs; 4,718 derived page-text files |
| Searchable-copy validation | All 74 qpdf-clean, readable and page-count matched |
| Structural check | 39 clean; 74 have qpdf stream warnings only; no fatal errors |

The warnings are characteristic of the scanned PDFs and do not indicate a bad
seller download: PDF metadata, Poppler rendering and text extraction all work.
Treat them as review metadata rather than a reason to reject an otherwise
readable file.

Detailed local reports:

- `preservation-verification.json`
- `archive-extraction-summary.json`
- `folder-archive-comparison.json`
- `analysis/pdf-inventory.json`
- `analysis/pdf-analysis-summary.json`
- `analysis/ocr-title-pages.json`
- `analysis/toolkit-ocr-batch-summary.json`
- `analysis/final-ocr-validation.json`
- `analysis/GM_SELLER_COVERAGE_MATRIX.md`
- `analysis/gm-manual-catalog.html`

## What the titles actually support

Folder names are only seller labels. A source title page or page content must
carry the year/model/engine evidence used for a result.

| Evidence group | What is supported so far | Important limit |
| --- | --- | --- |
| `1998-2007/2000 …` articles | 2000 or 2000–01 GM full-size truck/SUV systems, including Sierra, Silverado, Suburban, Tahoe, Yukon and Yukon XL | Not proof of all 2000–01 models or trims |
| `1998-2007/` 2002 articles | Many 2002 Sierra/Silverado and C/K articles, including engines, brakes, HVAC, driveline, electrical and wiring | Individual articles have their own engine/model exclusions |
| 2001–03 / 2003 articles | 6.6L diesel, Allison, transmission and 2003 Silverado 2500 HD fragments | Patchwork articles, not a complete HD manual |
| `2004-Chevrolet-Silverado.pdf` | 574-page 2004 Chevrolet Silverado owner manual | Owner information is not a service-manual substitute |
| `2006 - 2007/` | 30 native-text articles headed `2006 Chevrolet Silverado 1500`, covering chassis, driveline, brakes, HVAC, electrical, wiring and a 4.3L engine article | The contents inspected say 2006; the folder does not establish 2007 coverage |
| Trouble-code PDFs | Generic OBD-II and GM code lists | Not vehicle-specific diagnostic procedures |

One 2002 engine-performance article names a much wider GM model list, including
Aztek/Rendezvous, Avalanche, Escalade, Express/Savana, Blazer/Envoy/Jimmy,
S10/Sonoma/TrailBlazer and vans/minivans. That makes it potentially useful
evidence for those listed vehicles, but it does **not** establish a complete
manual set for any of them.

No standalone 1998, 1999 or 2007 service-title evidence was found. 2005 appears
in a `2003-05 FUSES.pdf` article only. Preserve each repeated system article as
separate source evidence because the year, engine and applicability qualifiers
can differ.

## OCR and reader preparation

The first title-page pass is saved under `analysis/ocr-title-pages/`. Full
searchable copies were derived separately under `analysis/toolkit-searchable/`.
They retain:

- original source SHA-256 and relative path;
- page count and original page number;
- native-text versus OCR-derived text provenance; and
- the actual title-page or page-level applicability evidence.

[workshop-manual-toolkit](https://github.com/abelmathews707/workshop-manual-toolkit)
is the local readability tool: it isolates image-only pages, OCRs them and
merges them back into a searchable PDF. Its default regular-PDF mode returns
exit code 4 after generating readable output because of nonfatal qpdf stream
warnings. A local compatibility runner retains the toolkit workflow but uses
PDF/A for the OCR-only temporary PDF. The completed batch has 74 clean outputs:
each has the original page count, final `qpdf --check` success and one derived
text file per source page. A fresh SHA-256 pass confirmed that all 113 original
PDFs still match the archive manifest after processing.

Open `analysis/gm-manual-catalog.html` locally to filter all 113 records and
click an original PDF or, for every scanned PDF, its derived searchable copy.
The catalog and the coverage matrix are convenience views; the original PDFs
remain the authoritative source for applicability.

## What this does and does not unlock

The PDF input is trustworthy enough for development fixtures and local
acceptance. It does **not** mean that GM import, search, citations, vehicle
selection, OCR handling or Repair Buddy integration exists yet. It also does not
remove the separate HTML USB integrity blocker.

The next shared implementation milestone is Step 2 in
[GM_HTML_PLAN.md](GM_HTML_PLAN.md): define a neutral format contract that can
describe both `workshop_manuals_html_v1` and a provisional `pdf_collection_v1`
without hard-coding GM or Ford behavior.
