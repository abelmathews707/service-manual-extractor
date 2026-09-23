# Service manual extraction contract v1

Status: manifest and operation contracts frozen by implementation Step 2;
neutral HTML/PDF source readers implemented in Step 3, content normalization
implemented in Step 4.

## Purpose and boundary

Future readers for Ford disc archives, self-contained HTML exports and PDF
collections must describe their output in the same manufacturer-neutral form.
Repair Buddy and a standalone viewer should be able to consume that form
without knowing which reader produced it.

Contract v1 has two machine-readable records:

- `service-manual-manifest/v1`: the durable source, publication, document,
  asset, applicability and citation record.
- `service-manual-operation/v1`: the JSON response used by neutral `probe` and
  `extract` commands.

The public JSON Schemas are
[`schemas/service-manual-manifest-v1.schema.json`](../schemas/service-manual-manifest-v1.schema.json)
and
[`schemas/service-manual-operation-v1.schema.json`](../schemas/service-manual-operation-v1.schema.json).
Step 3 adds a separately versioned raw-file inventory schema at
[`schemas/service-manual-source-inventory-v1.schema.json`](../schemas/service-manual-source-inventory-v1.schema.json).
[`sme/contract.py`](../sme/contract.py) is the dependency-free validator and ID
implementation used by this repository's Python tests. The manifest and
operation records remain frozen; future inventory changes require a new
inventory contract version.

The existing `python3 -m fsd` command remains the working Ford extractor. Step
2 does not change its commands, JSON, selection rules or exit behavior, and it
does not route Ford extraction through the new contract yet.

## Source formats and completeness

The declared format names are exact and versioned:

| Format | Meaning in v1 |
| --- | --- |
| `ford_tsp_disc_v1` | Ford `POD BAY` version 1 archive source |
| `ford_tsp_disc_v2` | Ford `BAY POD` version 2 archive source |
| `workshop_manuals_html_v1` | Self-contained workshop HTML export with local pages/assets |
| `pdf_collection_v1` | One or more original PDF publications |

Unknown input must fail detection. It must not be labeled with the nearest
known format. Merely containing HTML or PDF files is not enough to claim a
complete supported source.

`source.status` is one of:

- `complete`: every selected source item required by the reader passed its
  integrity checks; `failures` must be empty.
- `partial`: useful records exist, but one or more exact failures are retained.
- `failed`: the selected source cannot produce a usable manifest.

`partial` and `failed` require at least one failure containing a stable code and
human-readable reason. A related path is included when one specific member
failed. A publisher's intentional “content not included” page is represented
as `unavailable_by_source`, not silently turned into a procedure.

## Stable identity and paths

Every source, publication, document and asset has a deterministic ID:

```text
src_<32 lowercase hex characters>
pub_<32 lowercase hex characters>
doc_<32 lowercase hex characters>
asset_<32 lowercase hex characters>
```

The digest input is UTF-8 text separated by NUL bytes and begins with the fixed
namespace `service-manual-contract-v1`. Source IDs use format, container,
recorded identity and source SHA-256. Descendant IDs use their parent's ID plus
their canonical source-relative path. The exact algorithm lives in
`sme.contract.stable_id`.

Paths always use `/`, are relative to the selected source root, and may not
contain parent traversal, drive prefixes, UNC/absolute roots, NUL bytes or
control characters. Step 3 implements the archive defenses, collision checks
and staged copying described in [`SOURCE_READER_V1.md`](SOURCE_READER_V1.md).

Exact selection uses stable IDs. A short display code or duplicate filename is
never sufficient to choose one publication. This preserves the current Ford
rule that duplicate archive codes are selected by their exact source-relative
archive identity.

## Publications and documents

A manifest contains one source and zero or more publications. Each publication
records:

- its exact source entry path, title and kind;
- source-stated applicability evidence; and
- documents that keep their own paths, hashes, context and citations.

Publication kinds are `workshop`, `wiring`, `diagnostics`, `owner`, `reference`
and `unknown`. `unknown` is an explicit classification, not permission to treat
the publication as workshop information.

Documents retain breadcrumbs, applicability statements, references and assets.
Applicability is evidence, not an inferred vehicle-fit claim: the record keeps
the statement, its source path, its scope (`publication`, `document`, `table` or
`figure`) and an optional selector. Identical procedure text at two paths keeps
two document IDs, two applicability records and two citations. A content hash
may reveal duplication but must not erase context.

References have an exact target state:

- `resolved`: includes a target document ID;
- `missing`: the expected source path is absent;
- `outside_selection`: present elsewhere but not in the chosen publication;
- `unavailable_by_source`: the publisher explicitly omitted the content.

Unresolved references keep a reason and never invent a target.

## Text, PDFs, assets and citations

Every document records a content SHA-256 and at least one original citation.
HTML citations use an original path plus an optional fragment. PDF citations use
the original PDF path and a one-based page number.

Searchable text provenance is exact:

- `native`: text came from the original item and has its own hash;
- `ocr`: text is derived, retains the original item hash in
  `derived_from_sha256`, and names the OCR tool/version;
- `none`: no searchable text is claimed.

OCR never replaces or relabels the original PDF. Page citations continue to
resolve to that original file. Assets retain path, media type, hash, owning
document and caption. Step 4 implements the static SVG policy and page-content
sidecar described in [CONTENT_NORMALIZATION_V1.md](CONTENT_NORMALIZATION_V1.md).
For PDFs, a per-page document has a logical `.sme-derived/pages/...` record path
and cites its original PDF path/page. The logical path is not a reader file.

## Neutral command contract

The neutral entry point is `python3 -m sme`. Contract discovery and validation
remain available:

```sh
python3 -m sme contract --json
python3 -m sme validate-manifest MANIFEST.json --json
```

`contract` returns the exact format/status vocabulary and the implemented
HTML/PDF readers.
`validate-manifest` exits 0 for a valid manifest and 1 for invalid JSON or an
invalid contract record.

Step 3 implements the neutral source commands:

```sh
python3 -m sme probe SOURCE --json
python3 -m sme extract SOURCE -o OUTPUT --publication PUBLICATION_ID --json
```

Their JSON output is `service-manual-operation/v1` with these required fields:

| Field | Meaning |
| --- | --- |
| `operation` | `probe` or `extract` |
| `ok` | Whether the requested operation completed without an error |
| `source` | The same immutable source record used by the manifest |
| `publications` | Exactly selectable publication summaries |
| `output` | `null` for probe; manifest path and byte/file counts for extract |
| `diagnostics` | Structured warning/error code and message records |

`probe`/`extract` exit behavior is 0 for success, 1 for a completed
operation that found integrity/extraction failures, and 2 for invocation,
unreadable-input or unsupported-format errors. The JSON record must still name
an exact supported format; an unknown input cannot masquerade as a supported
format merely to produce an `ok: false` record.

## Synthetic acceptance examples

The committed HTML/SVG files under `tests/fixtures/html_manual` exercise an
index, numeric page paths, a diagnostic table, a captioned SVG, a short child
page, a missing target, an intentional unavailable-content page and identical
procedure text with different engine qualifiers. Tests generate a two-page PDF
in memory so no PDF/manual file is committed; one page records native text and
one records OCR-derived text.

`tests/test_contracts.py` also validates Ford v1/v2 records, freezes existing
Ford command names and probe JSON/exit behavior, and rejects unsupported formats
and unsafe paths. Reader behavior is covered separately by
`tests/test_sources.py`.
