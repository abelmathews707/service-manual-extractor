"""Authored association review; no automatic applicability/content approval."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from test_structured_contracts import TIMESTAMP, fixtures

from sme.continuation_review import (
    CHECKS,
    append_continuation_event,
    bind_continuation,
    new_continuation_review,
    resolve_reviewed_target,
    save_continuation_review,
    source_link_state,
    validate_review,
)
from sme.contract import ContractError
from sme.structured_contracts import seal_records


class ContinuationReviewTests(unittest.TestCase):
    def setUp(self):
        vocabulary, _, bundle, _ = fixtures()
        self.configuration = vocabulary['configurations'][0]['id']
        self.source = next(r for r in bundle['records'] if r['type'] == 'procedure_step')
        self.target = next(r for r in bundle['records'] if r['type'] == 'diagnostic_node')
        self.binding = bind_continuation(
            self.source, self.target, reference=self.source['original_text'],
            configuration_ids=[self.configuration])
        self.review = new_continuation_review()

    def append(self, action, **kwargs):
        self.review = append_continuation_event(
            self.review, self.binding, action=action,
            reviewer={'id': 'authored test reviewer', 'kind': 'agent'}, timestamp=TIMESTAMP,
            reason='Authored test, not a real manual approval',
            checks=dict.fromkeys(CHECKS, True), expected_revision=self.review['revision'], **kwargs)
        return self.review['events'][-1]

    def approved(self):
        self.append('propose')
        return self.append('approve')

    def quality(self, record):
        return {'state': 'approve', 'approved': True, 'record_id': record['id'],
                'record_sha256': record['record_sha256'], 'intended_use': 'readable_reference',
                'purpose': 'engineering'}

    def test_explicit_review_and_revocation_are_separate_from_record_quality(self):
        with self.assertRaises(ContractError):
            self.append('approve')
        event = self.approved()
        self.assertEqual(source_link_state(event, self.source, self.configuration, {}),
                         'source_quality_unapproved')
        self.assertEqual(source_link_state(event, self.source, self.configuration,
                                            self.quality(self.source)), 'available')
        revoked = self.append('revoke')
        self.assertEqual(source_link_state(revoked, self.source, self.configuration,
                                            self.quality(self.source)), 'revoke')

    def test_binding_checks_quotation_and_both_vehicle_configurations(self):
        for reference, ids in [('Invented source instruction', [self.configuration]),
                               (self.source['original_text'], ['cfg_' + 'f' * 32]),
                               (self.source['original_text'], [])]:
            with self.assertRaises(ContractError):
                bind_continuation(self.source, self.target, reference=reference,
                                  configuration_ids=ids)

    def test_source_changes_and_wrong_use_withhold(self):
        event = self.approved()
        changed = copy.deepcopy(self.source)
        changed['conditions'].append('new condition')
        changed = seal_records([changed])['records'][0]
        self.assertEqual(source_link_state(event, changed, self.configuration,
                                            self.quality(changed)), 'stale')
        for update in ({'state': 'revoke'}, {'intended_use': 'diagnostic_instruction'},
                       {'purpose': 'production'}, {'record_sha256': 'f' * 64}):
            self.assertEqual(source_link_state(event, self.source, self.configuration,
                                                self.quality(self.source) | update),
                             'source_quality_unapproved')

    def test_chain_tampering_invalid_checks_and_changed_binding_fail(self):
        self.approved()
        for mutate in (lambda e: e.update(parent_id='broken'),
                       lambda e: e['checks'].update(source_compared=False),
                       lambda e: e['binding']['target'].update(record_sha256='f' * 64)):
            value = copy.deepcopy(self.review)
            mutate(value['events'][-1])
            with self.assertRaises(ContractError):
                validate_review(value)

    def test_target_scope_is_checked_before_text_and_quality(self):
        load = Mock(return_value=[self.target])
        quality = Mock(return_value=self.quality(self.target))
        for state in ('excluded', 'possible', 'unreviewed'):
            result = resolve_reviewed_target(
                self.binding, self.configuration, scope_for=lambda *args, s=state: {'state': s},
                load_unit=load, quality_for=quality)
            self.assertEqual(result['state'], 'withheld')
        load.assert_not_called()
        quality.assert_not_called()

    def test_independently_approved_but_changed_target_does_not_retarget_link(self):
        changed = copy.deepcopy(self.target)
        changed['conditions'].append('new condition')
        changed = seal_records([changed])['records'][0]
        result = resolve_reviewed_target(
            self.binding, self.configuration,
            scope_for=lambda unit, cfg: {'state': 'confirmed', 'unit_id': unit,
                                         'configuration_id': cfg},
            load_unit=lambda unit: [changed], quality_for=lambda *args: self.quality(changed))
        self.assertEqual(result['state'], 'withheld')
        self.assertNotIn('record', result)

    def test_persistence_preserves_history_and_refuses_stale_writer(self):
        empty = self.review['revision']
        self.approved()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'continuation-review.json'
            save_continuation_review(path, self.review, expected_revision=empty)
            self.assertEqual(json.loads(path.read_text()), self.review)
            with self.assertRaises(ContractError):
                save_continuation_review(path, self.review, expected_revision=empty)
            current = self.review['revision']
            with self.assertRaises(ContractError):
                save_continuation_review(path, new_continuation_review(),
                                         expected_revision=current)
            self.append('revoke')
            save_continuation_review(path, self.review, expected_revision=current)


if __name__ == '__main__':
    unittest.main()
