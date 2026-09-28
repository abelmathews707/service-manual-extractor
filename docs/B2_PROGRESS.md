# B2 — Specifications and part references

Date: 2026-09-28. Status: extraction checkpoint implemented; application quality
review integration and final acceptance remain in progress. B3 has not started.
Branch: `codex/structured-specifications-b2`, based on accepted B1 `c52b1c3`.
Worktree: `/Users/asokmathews/Documents/service-manual-extractor-b2`.
Stop when either five-hour remaining reaches approximately 10% or weekly
remaining reaches 5%. Check both limits between implementation/verification chunks.

The bounded native extractor uses explicit structural recipes, not expected
numeric answers. It expands row/column spans, binds values to their original
header and unit, retains original wording and governing context, and never
borrows notes from another table. Missing, composite, footnoted, unsupported
and OCR values abstain or remain ambiguous; they are not silently corrected.
Native PDF regions reject clipped words and ambiguous/full-page grammar.
Printed identifiers are only mentions in a declared namespace, never inferred
fitment or supersession. No automatic quality or diagnostic approval is issued.

Local-only acceptance root:
`/Users/asokmathews/Documents/service-manual-data/b2-acceptance-2026-09-28`.
Structural rules are in `recipes.json`; `records-v1/verification.json` records
eight extracted records across two Ford units and a GM native-PDF abstention.
Three frozen B1 golden specification/part payloads and conditions match exactly.
GM's illustrative pressure/test example does not become a universal specification.
The unreviewed Ford workshop part mentions have no vehicle configuration IDs;
they cannot enter the selected V10 path. Originals and detailed values stay local.

Current checks: 225 extractor tests run, no failures, two optional Node-dependent
skips. Ruff passes. New authored tests cover spans, zero versus missing, units,
conditions, ambiguous rows, table-note boundaries, part namespaces, PDF grammar,
OCR abstention and wrong-vehicle rejection before HTML parsing.

Remaining before B2 closes: integrate typed reference display and separate
intended-use quality preview/commit into the scoped app reader, add stale/revoke
and forbidden-load tests, verify the original layouts and held-out typed values,
run full app/Ford/GM regressions and push the exact dependency pin. Do not merge,
activate the live database, claim production approval or begin B3 at this checkpoint.
