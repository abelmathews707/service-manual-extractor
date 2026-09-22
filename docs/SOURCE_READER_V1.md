# Neutral source reader v1

Status: implemented by Step 3 on 2026-09-22. This reader verifies and stages
original files; it does not yet interpret procedures, navigation, tables,
qualifiers, diagrams or searchable page text.

## Supported inputs

`python3 -m sme probe SOURCE` accepts:

- a ZIP containing one or more recognizable HTML workshop exports;
- an already-unpacked folder containing those exports;
- a folder or ZIP containing PDFs only; or
- one standalone PDF.

An HTML export must contain an `index.html` and at least one HTML file below its
matching `pages/` directory. A folder containing arbitrary HTML does not qualify.
A PDF folder name is never treated as evidence of vehicle, year, engine or
manual coverage. Until Step 4 reads source title evidence, PDF publication titles
are only their filenames and their kind is `unknown`.

Unknown inputs return exit code 2. A recognized but incomplete or unsafe input
returns exit code 1 and a structured `partial` result. A complete input returns
exit code 0.

## Safety and integrity policy

Every selected file is read completely and SHA-256 hashed before extraction.
ZIP reads therefore verify decompression, declared length and CRC. The reader
rejects or marks partial inputs containing:

- parent traversal, absolute, drive-letter, UNC/backslash, non-canonical or
  control-character paths;
- exact duplicate names or case/Unicode-normalization collisions, including
  conflicts in parent directory names;
- symbolic links, encrypted ZIP members or unsupported compression;
- corrupt/truncated members, files that change while being read, or files that
  change between inspection and copying; and
- configured file-count, individual-size, total-size or compression-ratio
  limit violations.

The default limits are 200,000 files, 1 GiB per file, 20 GiB total expanded
bytes and a 1000:1 per-member compression ratio. Limits are enforced from ZIP
metadata before decompression and again through actual read lengths/hashes.

`.DS_Store`, `Thumbs.db`, `__MACOSX` and AppleDouble `._*` files are the only
ignored operating-system metadata. They are listed in diagnostics and the
source inventory rather than silently disappearing. Empty files are preserved.
Explicitly empty directories are preserved; ordinary derived directory entries
do not affect content identity.

## Deterministic content identity

The reader records two different identities on purpose:

- The common manifest's source SHA-256 preserves container provenance. A ZIP
  identifies its original ZIP bytes; a folder identifies its canonical member
  inventory.
- The source inventory's content SHA-256 is calculated from relative path,
  byte length and SHA-256 for every readable file plus empty directories. The
  same ZIP and unpacked folder therefore describe the same content while still
  retaining different source/container IDs.

Same-sized file changes alter the content identity. Duplicate basenames in
different folders stay distinct because their complete relative paths remain
part of every record.

## PDF page counts

Every PDF gets an original-file SHA-256 and page count during inspection. When
Poppler's `pdfinfo` is available it is used as the full PDF reader. A
dependency-free structural fallback handles straightforward PDFs; it refuses
encrypted files or PDFs whose compressed object structure cannot be counted
confidently. The inventory records which method produced each count.

Page content, native text and OCR-derived text are Step 4 responsibilities.
This step never overwrites or relabels an original PDF.

## Exact selection and atomic extraction

Probe first to obtain stable publication IDs:

```sh
python3 -m sme probe SOURCE --json
python3 -m sme extract SOURCE -o FRESH_OUTPUT \
  --publication pub_0123456789abcdef0123456789abcdef --json
```

Omit `--publication` to select every detected publication. The output path must
not already exist, must not be under a folder source, and its immediate parent
may not be a symbolic link. Extraction:

1. repeats complete source inspection;
2. copies only exact selected paths into a fresh sibling staging directory;
3. verifies copied byte counts and hashes;
4. writes `.sme-manifest.json` and `.sme-source-inventory.json`; and
5. atomically renames the staging directory to the requested destination.

Cancellation or any error removes staging and leaves the destination absent.
A rerun never merges with or overwrites existing output. A partial source is
reported but never published. Recovery of damaged input must be a separate
operation with its own source identity and incomplete status.

The common manifest intentionally contains empty document arrays at this step.
Step 4 will normalize verified original files into cited documents without
changing their recorded source identity.

## Local acceptance results

Read-only checks on the preserved 2026-09 GM inputs produced:

| Input | Result |
| --- | --- |
| Seller PDF folder | Complete: 113 PDFs, 12,324 pages, no failures |
| Seller PDF ZIP | Complete: 113 PDFs, 12,324 pages, no failures |
| Matching unpacked ZIP root | Same content SHA-256 as the ZIP: `b88d90f9675e18fd241eb8653d3b24de2d6232d749aacc1a999ccd80eb105a4a` |
| Original 6.6L HTML ZIP | Partial: 60,009 readable files and 760 exact unreadable-member failures |
| Original 8.1L HTML ZIP | Partial: 54,998 readable files and 5,483 exact unreadable-member failures |
| Original 6.0L HTML ZIP | Rejected before publication: corrupt ZIP extra-field/directory structure |

These reproduce the earlier preservation findings. They do not expand vehicle
coverage or make the damaged HTML sources complete.
