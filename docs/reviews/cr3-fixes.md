# CR3 — Extractor review fixes

Implemented 2026-10-05, following `cr1b-extractor.md` and Repair Buddy's
`docs/reviews/cr2-fix-decisions.md`. These are implementation and local regression
results, not independent CR6 sign-off or approval of a real diagnosis.

## What changed

| Finding | Change | Regression proof |
| --- | --- | --- |
| CR1A-01 / CR1B-2 | The manifest binds the complete original-file inventory by a canonical SHA-256. Extraction, normalization, evidence, OCR planning and library admission check that binding. | Altered originals plus rewritten inventories are rejected for authored HTML, PDF and Ford packages. App tests additionally cover assets, reading and reimport. |
| CR1B-1 | Simple explicit VIN/other variant restrictions survive interpretation. Unknown, exclusion and multiple-value wording stays unconfirmed. Narrow native restrictions take priority over broad vehicle headings. | Full extraction → evidence → matching permits VIN W and excludes VIN X for otherwise identical vehicles. `except`, unknown values, `or`, slash and comma lists stay unresolved. |
| CR1B-3 | First and cached imports retain normalized status and failures. The folder command returns nonzero for selected partial results. Partial packages cannot enter the verified searchable library. | Authored unreadable HTML remains partial on first run, cache reuse and CLI; complete packages still pass the existing suite. |
| CR1B-4 | Automatic discovery requires a declared Ford publication, not just an archive filename. Unknown archives in otherwise recognized media are listed as skipped. | Generic POD remains unsupported; a mixed source imports its recognized Ford archive and reports the other archive. |
| CR1C-02 | The legacy Ford viewer allowlists static HTML, removes executable attributes/remote resource URLs and sanitizes SVG before publication. Unsupported SVG gets an explicit unavailable placeholder. | Generated local text and diagrams survive; authored active HTML/SVG cannot run handlers or request their supplied resource URL in a real Chrome/Playwright test. |

Search export revision hashing now includes source identity, evidence and vehicle
interpretation rules. Extraction cache keys include the new identity/sanitizer
code. Cached evidence is compared with current capture rules, not silently reused
after interpretation changes.

## Upgrade requirements

Old packages without `source.inventory_sha256` are readable under the schema but
are **not admitted by the verified pipeline**. Re-extract from the unchanged owned
originals into new output folders, normalize, regenerate evidence, rebuild the
library and review changed evidence before use. Do not copy a new checksum into
an old package or carry old acceptance forward merely to bypass a rejection.
Keep old outputs and review records for comparison; this change does not rewrite
or delete them. Repair Buddy schema 4 separately withholds old active generations
until a new verified generation is imported.

Automatic no-EPL archive recognition is intentionally unsupported; no verified
exception was introduced. The explicit legacy Ford import path remains, but
the automatic folder workflow will not guess an unknown archive's manufacturer.
Some SVG features or inline styling may no longer render in the legacy viewer;
unsupported diagrams are labeled, not served unsanitized. Broad real-manual visual
compatibility still belongs to CR6.

## Verification

- 335 extractor tests passed, zero skips, with optional PDF/JSON schema/OCR
  dependencies, real OCR and the real-browser security check enabled.
- Ruff and `git diff --check` passed.
- On an archived copy of the reviewed `a6db8a0` code, the five new authored
  regression methods reproduced the original failures. The partial-import
  assertion specifically observed `processed` instead of `partial`.
- No owned manuals were processed or admitted. No paid AI request, real
  diagnostic approval, toolkit modification, release or merge to `main` occurred.
- Local checks used macOS, Python 3.14.7 and Ruff 0.16.9. Existing legacy file
  handle ResourceWarnings were suppressed for the suite; the PyMuPDF `fitz`
  deprecation notice remains. This is not a claim of new cross-platform CI.

Example full check (set paths for your installed dependencies):

```sh
TOOLKIT_ROOT=/path/to/workshop-manual-toolkit \
RUN_REAL_OCR=1 REPAIR_BUDDY_TEST_CHROME=/path/to/chrome \
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -q
ruff check .
git diff --check
```

The browser check also needs `node` on PATH and Playwright discoverable by Node
(for example via NODE_PATH). Without those options, the optional tests skip;
do not report the same coverage as the enabled run.

## Next

Repair Buddy pins the exact tested extractor code and repeats integration tests.
CR4 measures performance before proposing optimization; CR5 is selected cleanup;
CR6 independently reviews the combined exact versions before release preparation.
The app's deferred human-evaluation binding issue remains a DV2/DV3 gate.
