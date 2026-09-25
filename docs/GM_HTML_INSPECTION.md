# GMC USB manual inspection

Date: 2026-09-15
Status: Initial format investigation complete; input integrity unresolved.

## Summary

The USB contains three static HTML exports labelled GMC Sierra 2500 HD 6.0L,
6.6L and 8.1L, plus a Windows instruction video and its macOS metadata file.
The structure is suitable for a new HTML-format adapter. The archive contents
are damaged/incomplete, and the 6.0L source did not produce stable read hashes.
These inputs are useful for format investigation but do not pass acceptance
as complete, validated manuals.

## Preservation and local locations

Source folder:

`/Volumes/NO NAME/GMC SIerra 2500 HD 2001 - 2006 Manual`

Local inspection root:

`/Users/asokmathews/Documents/service-manual-data/gm-usb-2026-09-15`

The source folder's five files were copied with `rsync -rt` (842,021,746 bytes).
USB system/Spotlight folders were outside the selected manual folder and were
not copied. All commands treated source files as read-only; no source software
or manual JavaScript was executed. Everything listed below stays outside Git.

| Relative local path | Contents |
| --- | --- |
| `original/` | First copies of all three ZIPs, video and metadata file |
| `second-copy/` | Separate second 6.0L ZIP copy after the mismatch |
| `extracted/6.6L/2001 - 2006 GMC Sierra 2500 HD 6.6L/` | Successfully read and CRC-checked files only; incomplete images |
| `extracted/8.1L/2001 - 2006 GMC Sierra 2500 HD 8.1L/` | Successfully read and CRC-checked files only; incomplete HTML |
| `recovery/6.0L-directory-rebuilt.zip` | Derived `zip -FF` experiment; still invalid, not an accepted replacement |
| `recovery/6.0L-zip-repair.log` | Recovery command output |
| `copy-verification.json` | Source and first-copy SHA-256 checks for all five files |
| `6.0L-second-copy-verification.json` | Second-copy hashes and source reread mismatch |
| `extraction-summary.json` | Counts and every failed/rejected member, including failed 6.0L recovery |
| `6.6L-file-manifest.json`, `8.1L-file-manifest.json` | Successful member paths, lengths, SHA-256 and expected ZIP CRC |
| `sample-structure.json` | Static inspection of entry pages, navigation, procedures and references |
| `inspect_local.py`, `recopy_60.py` | One-off local investigation scripts, not production adapters |

The extraction script prechecked member paths/types, encryption, duplicate
case/Unicode paths and declared size/count bounds. Each successful output was
read to completion, verified by ZIP CRC, checked for length and SHA-256 recorded.
Failed partial output files were discarded; successful outputs and originals
remain. This is an inspection procedure, not a production hardening claim.

## Integrity results

Counts exclude four directory entries per readable ZIP.

| ZIP label | ZIP bytes | Listed files | Successfully extracted | Failed | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| 6.0L | 266,881,154 | Unknown: invalid directory | 0 | Unknown | Repeated source-read hashes differ; original and rebuilt directories rejected |
| 6.6L | 276,361,375 | 60,769 | 60,009 | 760 | Copy matches source; 2 GIF, 615 PNG and 143 JPEG files fail |
| 8.1L | 276,316,917 | 60,481 | 54,998 | 5,483 | Copy matches source; 5,483 HTML files fail |

The 6.6L archive lists 52,878 HTML files; all were extracted successfully.
The 8.1L archive lists 52,590 HTML files; 47,107 were extracted successfully.
Failures include bad local-header signatures and decompression/CRC errors.
No unsafe/duplicate/encrypted entries were rejected in the two readable listings.
Successful outputs total 960,672,037 content bytes across 115,007 files.

The video and metadata file hashes matched their USB source. The following
stable source-matching ZIP hashes identify the tested inputs:

```text
6.6L a6265970274f4da75452476fd6baf03670dd9cc96583aacd564b7c7f1c570248
8.1L 2505cade2f6ed87d9663c93e2fcf086d96a978ce43a47e2c118adeaead38c688
```

The 6.0L evidence is materially different:

```text
First local copy:   8f0f7389889347161dcf3c111fe0382b9e4923bf97c7bc09da49ba8801c62709
First USB re-read:  df7b8f8ce4cd2291e677c73d28d046a9d98c3a759e499d502e68c1248f47c451
Second copy/read:   f314d009edc8d352028ef036d390f96d538acdc5497f1fb7d4373488001b0fb8
Next USB re-read:   2bf6146ccd06dcd8c16b1f9a32032da12b6087d6f557beb44e8d03bda20364c7
```

The first local copy was rehashed and remained unchanged. The second copy
matches the byte stream read while copying, but not the subsequent USB read.
The root cause of the inconsistent USB reads has not been established. Do not
attribute the problem to the future importer or assert a specific hardware fault.

Python rejected the 6.0L central directory with `Corrupt extra field 6b29`.
`unzip` and `bsdtar` also reported directory damage. A recovery experiment
against the second local copy returned exit code zero from `zip -FF`, but its
output still failed Python validation (`Corrupt extra field fe8d`). This is
direct evidence that a recovery command's exit code is insufficient validation.
No extracted 6.0L manual or verified complete archive is claimed.

## Actual vehicle coverage

The 6.6L and 8.1L root indexes identify **2006 GMC Sierra 2500 HD, 2D Pickup,
4WD, Automatic**, with engine strings `6.6 2` and `8.1 G` respectively.
The 6.6L index also claims compatibility with `6.6 D` and other cab variants;
both indexes describe related variants as sharing much of the manual.

These are source claims, not independently reviewed fitment. The 2001–2006 ZIP
names do not establish 2001–2005 coverage. The 6.0L selected vehicle has not
been established from a validated extraction.

The selected-vehicle title is not enough to qualify individual instructions:

- `pages/100.html` explicitly warns that the labor information is for Sierra
  1500 with a `4.3 X` engine.
- `pages/1000.html` contains six figures captioned for 6.0L CNG power
  distribution, even in the 6.6L and 8.1L archives.
- Diagnostic tables can contain engine-specific rows/values. Preserve these
  qualifiers when indexing, grouping aliases and assembling evidence.

## Export structure and reusable parsing rules

The visible branding is “Workshop Manuals,” with a 2025 retrieval statement.
The observed layout is:

```text
<ZIP label>/
  index.html
  404.html
  external-car.html
  script.js
  style.css
  icons/*.svg
  images/*.{svg,png,jpeg,gif}
  pages/<numeric ID>.html
```

Use format detection rather than assuming this is the structure of every GM
manual. SVG metadata contains a Mitchell1 enrichment namespace, but that alone
does not establish the exact exporter product or original publication provenance.

The inspected script handles folding navigation, fragment-based folder opening
and session scroll state. Content already exists in the HTML; no browser/script
execution is required to discover or extract it. The two readable archives share
the inspected script/style contents.

- Main content: `.main`; section title: `.main > h1`.
- Hierarchy: `.header .breadcrumb-part`.
- Exclude repeated `.footer` and `.branding` from searchable text.
- Variant warning: `.other-warning.other-variant`.
- `pages/2.html` is a navigation tree; `pages/3.html` is an expanded tree, about
  2.4 MB with 24,755 anchors for 6.6L and 24,260 for 8.1L.
- Nested `ul`/`li.li-folder` and named anchors describe folder structure;
  some structural anchors have no `href`.
- Relative paths include `../pages/2412.html` and percent-encoded fragments;
  images use paths such as `../images/GM1156070.png`.
- `404.html` duplicates the vehicle landing page. Its Home/GMC/2006 links do
  not prove other vehicles or years are included.
- `external-car.html` is a deliberate omitted-other-vehicle notice. The inspected
  footers also refer to an absent `about.html`.

The extracted-file check found 526 distinct unavailable targets referenced by
the 8.1L expanded tree, including the absent footer target. Its otherwise
readable oil-pressure-gauge page also has 12 distinct unavailable targets.
The corresponding sampled 6.6L pages only lacked the footer target. This is
why a readable procedure is not sufficient: its next diagnostic branch may
still be missing. These are sampled path-existence checks, not a full anchor audit.

## Procedures, diagrams and context

- `pages/2412.html` contains an oil-pressure-gauge diagnostic table with Step,
  Action, Values, Yes and No columns. `pages/3738.html` and `pages/6193.html`
  repeat the material under different navigation paths.
- `pages/1066.html` has a short Circuit Description heading whose breadcrumb
  supplies DTC B1017/B3970. Indexing the heading alone loses the diagnostic topic.
- `pages/10000.html` contains seven PNG connector views and tables linking
  pin, wire color, circuit and function.
- SVG diagrams appear in `.imageHolder.svgImageHolder`, with a preceding
  `.imageHeader .imageCaption`; original source API URLs can remain in metadata,
  while the actual image `src` points to the local `images/` directory.
- `images/VA229217.svg` is a local vector wiring figure, byte-identical in the
  two inspected ZIPs. Its source data includes text/path geometry and enrichment
  metadata. Current checked raster-preview behavior needs deliberate SVG support.

These observations were checked by static member reading and selected extracted
HTML parsing. No complete all-page reference/anchor audit or browser acceptance
test was performed. Those are planned gates, distinct from the complete member
integrity scan of the 6.6L and 8.1L inputs.

## Next action

Request trustworthy replacement/download copies or otherwise resolve input
integrity in Step 1. Preserve the current evidence to compare replacements.
Design and synthetic development can proceed from the observed format while
that is pending, but live-manual completeness and acceptance cannot pass yet.

The user confirmed there is no separate original download and plans to contact
the eBay seller. A concise report for the seller:

> The 6.6L ZIP has 760 unreadable image files; the 8.1L ZIP has 5,483 unreadable
> HTML files. Both local copies match the USB checksums. The 6.0L ZIP has a
> damaged directory and repeated reads from the USB give different checksums.
> Please provide clean replacement files or a download. Also, the 6.6L/8.1L
> start pages identify 2006, although the ZIP names advertise 2001–2006; please
> confirm where the other years are covered.
