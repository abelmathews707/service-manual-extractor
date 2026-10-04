"""Scope recapture must preserve evidence identity and never reuse approvals."""

import copy
import unittest
from unittest.mock import patch

from test_matching_review import _alt, _assertion, _base, _set_assertions

from acceptance.b3_symptom_scope import compare
from sme.applicability_contracts import evidence_revision, unit_id
from sme.contract import ContractError


class SymptomScopeTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary, self.manifest, self.after, _ = _base()
        unit = self.after['units'][0]
        unit['kind'] = 'section'
        unit['id'] = unit_id(self.after['generation_sha256'], unit['document_id'],
                             unit['kind'], unit['selector'])
        _set_assertions(self.after, _assertion(
            self.after, unit['id'], [_alt(self.vocabulary['configurations'][0])]))
        self.before = copy.deepcopy(self.after)
        self.before['units'][0].update(mixed_content=True, search={'state': 'metadata_only'})
        self.before['revision'] = evidence_revision(self.before)
        self.configs = dict(zip(('diesel', 'other', 'electric'),
                                self.vocabulary['configurations']))
        self.path = unit['citation']['path']

    def compare(self):
        with patch('acceptance.b3_symptom_scope.TARGET', self.path), \
                patch('acceptance.b3_symptom_scope._configs', return_value=self.configs):
            return compare(self.before, self.after, self.manifest, self.vocabulary)

    def test_real_matcher_excludes_other_vehicles_without_review_reuse(self):
        originals = copy.deepcopy((self.before, self.after))
        report = self.compare()
        self.assertEqual(len(report['changed_units']), 1)
        decisions = report['fixture_decisions']
        self.assertEqual(decisions['diesel']['before']['reason_codes'], ['mixed_content'])
        self.assertEqual(decisions['diesel']['candidate']['state'], 'confirmed')
        self.assertFalse(decisions['other']['candidate']['search_eligible'])
        self.assertFalse(decisions['electric']['candidate']['search_eligible'])
        self.assertEqual(report['review_events_added'], 0)
        self.assertFalse(report['diagnostic_ready'])
        self.assertFalse(report['library_activated'])
        self.assertEqual((self.before, self.after), originals)

    def test_tampered_snapshot_rejected(self):
        self.after['units'][0]['mixed_content'] = True
        with self.assertRaises(ContractError):
            self.compare()

    def test_unresolved_candidate_cannot_be_reported_as_fixed(self):
        self.after = copy.deepcopy(self.before)
        with self.assertRaisesRegex(ContractError, 'false positive'):
            self.compare()

    def test_changed_applicability_statements_rejected(self):
        _set_assertions(self.after, _assertion(
            self.after, self.after['units'][0]['id'],
            [_alt(self.vocabulary['configurations'][1])]))
        with self.assertRaisesRegex(ContractError, 'applicability statements'):
            self.compare()

    def test_changed_content_generation_rejected(self):
        self.after['content_sha256'] = '9' * 64
        self.after['revision'] = evidence_revision(self.after)
        with self.assertRaises(ContractError):
            self.compare()


if __name__ == '__main__':
    unittest.main()
