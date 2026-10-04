# Reviewed continuation references — B3

This is engineering **readable-reference** navigation, not diagnostic execution.
A source association, vehicle applicability, and content quality are three separate
reviews. Approving one never approves the others or changes a record's completeness.

## Stored contract

Each source unit can have `continuation-review.json` beside `records.json` and
`quality.json`. `sme.continuation_review` owns `continuation-review/v1`:

- A binding contains source and destination record IDs, unit IDs and exact record
  hashes; reviewed configuration IDs; and the exact source reference quotation.
  Record hashes cover locators, original source hashes, extraction revisions,
  conditions and applicability. No filename search or URL fallback is permitted.
- An append-only event log contains declared reviewer identity/kind, timestamp,
  reason, comparison checks and chained event hashes. The association ID is stable
  across record-content revisions, so a changed endpoint does not silently become
  an approved new destination.
- Transitions are propose → approve/reject, approve → revoke, and revoke/reject →
  propose. Approval requires source comparison, destination comparison and preserved
  conditions. Re-review a changed approved link by revoking it and proposing the
  new binding; never edit history. Multiple conditional targets remain separate
  associations; a partial link list is not a complete diagnostic graph.
- This is local declared engineering review, **not authenticated production
  authorization**. Hashes detect accidental changes, not a malicious local author
  rewriting an entire log. No real manual association is automatically approved.

## Creating a reviewed association

The current authoring interface is Python, not a new application review form:

1. Independently scope and validate both unit bundles against current originals,
   metadata and vocabulary. Compare both original locators and all relevant
   conditions. If either endpoint lacks vehicle applicability, stop.
2. Call `bind_continuation(source_record, target_record, reference=exact_quote,
   configuration_ids=[...])`. It checks current identities, quotation and both
   endpoint configuration lists. This creates a binding, not approval.
3. Load the existing log or call `new_continuation_review()`. Append a `propose`
   event using `append_continuation_event`, passing the current `expected_revision`,
   declared reviewer, timestamp, reason and the three boolean comparison checks.
4. After original comparison, separately append `approve` against that unchanged
   proposal. Persist using `save_continuation_review(..., expected_revision=...)`.
   Serialize writers with the application's review lock; the saver provides atomic
   replacement, revision comparison and history-prefix checks, not a process lock.
5. Independently use the existing structured-quality workflow for each endpoint's
   readable-reference quality. The link log does not manufacture these approvals.

Keep manual wording and review logs outside Git. A safe reviewed association can
still remain unavailable if its destination or dependencies subsequently change.

## Opening a link in Repair Buddy

The app first resolves a confirmed source vehicle scope and current source quality,
then loads the source's reviewed association metadata. It resolves the destination's
own **confirmed** membership before opening its original or typed text. General
reference-only, possible-match and Browse all modes cannot satisfy this check.

After original/source validation, `resolve_reviewed_target` calls the one-hop
`resolve_continuation` primitive. Destination configuration, record identity,
current readable-reference quality (including dependency hashes), and exact
reviewed destination hash must all match. The app rechecks the source link/review
and vehicle-review revision before returning the result. Missing, changed, revoked
or excluded destinations return an unavailable state with a source return link;
they do not trigger searches for replacements.

The reader preserves original wording, context, required tools, conditions and
branches, and offers comparison with the original destination. Incomplete records
remain visibly incomplete. Only one hop is opened per request: there is no recursive
expansion, so self-links and cycles cannot loop or exhaust an expansion budget.
Opening further links repeats these checks. Automatic complete-graph expansion
and complete real-manual acceptance are still pending B3 work.

## Verification

Extractor tests exercise explicit review transitions, both endpoint configurations,
original quotation, stale endpoints, independent quality, zero excluded-target text
loads, atomic persistence and retained history. App tests exercise the actual route's
scope-before-original ordering, possible/reference-only rejection, unavailable states,
one-hop cycles, source revocation during lookup and escaped original links.

Run app dependency-integration tests with `REPAIR_BUDDY_TEST_EXTRACTOR` pointing at
the independently versioned extractor checkout. Those tests create two authored
temporary units and use the real extractor validator and quality resolver, including
changed-warning dependency and revoked-quality cases. They do not approve real
manuals and do not replace the pending original-reviewed full-procedure benchmark.
