# CR1B — Service Manual Extractor review

Reviewed 2026-10-05. This is a code review with small, authored reproductions, not a new acceptance run on owned manuals or a judgment of diagnostic accuracy.

## Exact versions and scope

- Extractor code and clean starting tree: `codex/procedure-structure-b3` at `a6db8a05db94c5c80cc5943226cf63dacb93e721`. The report-only commit following this review does not change that code baseline.
- Repair Buddy code baseline: `9ce84b8f5bdbfc62017daaa893d6d1c6fc78fa57`; D0/CR0 documentation was read in the app worktree. Its active `config/service-manual-extractor.lock.json` still pins the extractor code commit above. The app code, dependency pin, and owner data were not changed.
- Workshop Manual Toolkit remains at `d150e7d889eb55ebba85065da264ab2bc414755d`; no toolkit files were touched.

Read the D0 and CR0 reports, CR1B packet, extractor handoff, the neutral source/provenance contracts and schemas, `sme/source.py`, `normalize.py`, `pdf_content.py`, `html_content.py`, `discovery.py`, `orchestrate.py`, `ford_adapter.py`, `evidence.py`, `vehicle_interpretation.py`, `matching.py`, `structured_extract.py`, the B3 procedure/continuation modules, and relevant `fsd/` archive/disc/extraction code. Traced the tests for source handling, evidence, normalization, matching, and B3 procedures. CR0 already passed all 329 extractor tests with optional dependencies and 320 app tests; those full suites were not rerun.

The source reader rejects unsafe ZIP member paths, symlinks, collisions and declared expansion limits before publishing. The neutral extractor copies to a sibling staging tree, checks the copied hashes, and atomically publishes only a complete source. Normalization preserves original files and page/path citations; native and OCR text have distinct provenance, and an OCR map binds its derived PDF to the original hash and page count. B3 decision and ordered-step extraction keeps unresolved continuations incomplete and requires confirmed scope before reading. These are code observations within the paths reviewed, not a claim that all possible source files or real procedures were validated.

## Findings, in priority order

### CR1B-1 — P1: VIN-restricted wording can confirm the wrong variant

**Where:** `sme/vehicle_interpretation.py:82-156` builds alternatives with `qualifiers: {}`; `sme/evidence.py:158-169` marks a resolved native statement as `source_supported`; `sme/matching.py:69-86, 343-359` then treats the absent VIN predicate as a match for either selection. `sme/html_content.py:87-91, 317-338` captures VIN wording as source evidence. The stricter B2 table-row guard in `sme/structured_extract.py:139-168` does not protect ordinary evidence and search scope.

**Impact:** A page explicitly limited to VIN W can be admitted as confirmed, searchable manual text for an otherwise identical VIN X vehicle. This crosses the shared vehicle gate before search and could also feed downstream assistant evidence.

**Evidence:** An authored, temporary HTML manual page contained `2003 Ford F-250 6.0L diesel VIN W only`. The test vocabulary had two configurations with the same make/model/year/engine and `vin` qualifiers W and X. After `extract_source`, `normalize_source`, and `capture_evidence`, the statement's assertion was `source_supported` but its alternative had `qualifiers: {}`. `match_unit` returned `confirmed`, reason `explicit_source`, and `search_eligible=True` for **both** configurations. A direct `interpret_statement` check returned `resolved=True` and `_alternative` matched W and X. No owned manual was involved.

**Suggested fix:** Parse a recognized VIN/RPO qualifier into a source-bound predicate only when its meaning and vocabulary mapping are unambiguous. Otherwise keep the original wording but downgrade the assertion to a proposal or unknown qualifier so it cannot produce confirmed membership. Apply the same conservative rule to other explicit qualifiers that the interpreter currently drops. Add a full extract → evidence → match regression with two same-engine VIN variants, plus an `except VIN ...` exclusion case and an app pre-search eligibility check.

### CR1B-2 — P1: an incomplete normalized update is reported as processed, and cached failures disappear

**Where:** `sme/normalize.py:214-242, 477-499` deliberately publishes a `partial` content package with exact failures. `sme/orchestrate.py:40-53` verifies cached content but returns only publication count. `sme/orchestrate.py:128-161` labels new and cached packages `processed` regardless of content status; cached package entries omit failures. `sme/cli.py:250-273` returns success for `process-folder` unless an exception occurs.

**Impact:** A caller using the outer processing result or exit code can treat a failed update as complete. A second run makes the failure less visible: the same partial package is reported as cached and has no failure field in its result. The package's `.sme-content.json` still says `partial`, so this is a reporting/admission failure, not a claim that the failure record was erased from disk.

**Evidence:** An authored temporary HTML source had valid `index.html` and one valid page plus `pages/bad.html` with unsupported declared encoding. First `process_folder` run returned row status `processed`, package `cached=False` with `html_normalization_failed`, while content status was `partial`. The second run returned `processed`, `cached=True`, no package `failures` field, and the same on-disk partial content/failure. The destination was a throwaway directory outside the source.

**Suggested fix:** Return content status and failures from cached verification and new builds; surface `partial` in each processing row and the top-level summary, and make the command exit unsuccessfully for any selected partial package. Decide explicitly whether a partial package may be published as a readable inspection artifact; never present it as a completed import. Test first-run and cached rerun status, JSON/plain CLI exit, and a failed new generation beside a previously complete one.

### CR1B-3 — P2: generic POD archives are routed through the Ford importer without Ford evidence

**Where:** `sme/discovery.py:34-49, 67-76` routes any `content/**/*.arc` folder to `ford-import` after the POD parser accepts it. `sme/ford_adapter.py:102-120` lists an archive even when `book_of` returns no Ford EPL book. `fsd/disc.py:381-410` invents a fallback book, and `sme/ford_adapter.py:566-797` publishes a `ford_tsp_disc_v2` package from it.

**Impact:** An unrelated POD archive in a similarly named directory receives Ford source-format identity and is processed by Ford-specific content rules. Without an EPL, the resulting package has no credible Ford publication identity or applicability. The current synthetic example had no searchable text, so wrong-vehicle exposure was **not** demonstrated here; the confirmed problem is format routing and misleading provenance.

**Evidence:** A temporary `generic-pod/content/books/NONFORD.arc` containing only `README.TXT` and no EPL was reported by `discover_folder` as `recognized`, route `ford-import`, with empty book type/title. `process_folder` then returned `processed`, one package, and zero failures. Its bytes were created by the test POD writer; no owned media was read.

**Suggested fix:** Require positive Ford publication evidence before automatic Ford routing, or quarantine archives without it as unknown/unsupported for an explicit review path. Preserve legitimate Ford archives that lack an EPL only under a documented, source-verified exception. Add a generic POD negative test and a genuine Ford-without-EPL compatibility test before choosing the rule.

## Limits and next step

Only temporary synthetic inputs were used for new reproductions. I did not reread or OCR the owned Ford/GM collection, render every HTML/SVG variant, test interrupted writes on a live volume, or independently compare B3 procedure wording with original Ford/GM manuals. The PDF fallback page counter, filesystem race behavior under a hostile concurrent writer, and all manufacturer-specific archive variants were inspected only in code, not exhaustively fuzzed. Full browser behavior and app data/AI boundaries belong to CR1A/CR1C.

CR2 should reproduce and rank these against the release scope, assign extractor fixes, and add regression checks before CR6. Recommended CR2 model is GPT-6 Sol / High per the development plan; the VIN gate may warrant GPT-6 Astra / High if its correction changes shared app/extractor applicability rules. Keep the app pinned to `a6db8a05db94c5c80cc5943226cf63dacb93e721` until a replacement code revision passes coordinated checks.
