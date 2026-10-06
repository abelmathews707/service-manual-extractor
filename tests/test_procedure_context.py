"""Continuation eligibility must precede any target-text load."""

import copy
import unittest
from unittest.mock import Mock

from test_structured_contracts import fixtures

from sme.contract import ContractError
from sme.procedure_context import resolve_continuation


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        vocabulary, _, bundle, _ = fixtures()
        self.record = next(r for r in bundle['records'] if r['type'] == 'procedure_step')
        self.configuration = vocabulary['configurations'][0]['id']
        self.unit = self.record['binding']['unit_id']
        self.scope = Mock(return_value={'state': 'confirmed', 'unit_id': self.unit,
                                      'configuration_id': self.configuration})
        self.loader = Mock(return_value=bundle['records'])
        self.quality = Mock(return_value={
            'state': 'approve', 'approved': True, 'record_id': self.record['id'],
            'record_sha256': self.record['record_sha256'],
            'intended_use': 'structured_reference', 'purpose': 'engineering'})

    def resolve(self, **kwargs):
        return resolve_continuation(self.record['id'], self.configuration,
                                    {self.record['id']: self.unit}, scope_for=self.scope,
                                    load_unit=self.loader, quality_for=self.quality, **kwargs)

    def test_each_target_requires_its_own_scope_before_loading(self):
        for changes in ({'state': 'excluded'}, {'state': 'possible'},
                        {'unit_id': 'wrong'}, {'configuration_id': 'wrong'}):
            self.scope.return_value = {'state': 'confirmed', 'unit_id': self.unit,
                                       'configuration_id': self.configuration} | changes
            self.assertEqual(self.resolve()['state'], 'withheld')
        self.loader.assert_not_called()
        self.quality.assert_not_called()

    def test_quality_is_independent_current_and_named_use_specific(self):
        approved = copy.deepcopy(self.quality.return_value)
        for changes in ({'state': 'stale', 'approved': False}, {'state': 'revoke'},
                        {'record_sha256': 'wrong'}, {'intended_use': 'readable_reference'},
                        {'purpose': 'production'}, {'record_id': 'another'}):
            self.quality.return_value = approved | changes
            result = self.resolve()
            self.assertEqual(result['state'], 'withheld')
            self.assertNotIn('record', result)
        self.quality.return_value = approved
        self.assertEqual(self.resolve()['record']['id'], self.record['id'])

    def test_missing_or_changed_target_never_becomes_available(self):
        self.loader.return_value = []
        self.assertEqual(self.resolve()['state'], 'unresolved')
        changed = copy.deepcopy(self.record)
        changed['payload']['instruction'] = 'changed without review'
        self.loader.return_value = [changed]
        with self.assertRaises(ContractError):
            self.resolve()

    def test_missing_locator_does_not_search_for_substitutes(self):
        result = resolve_continuation('unknown', self.configuration, {}, scope_for=self.scope,
                                     load_unit=self.loader, quality_for=self.quality)
        self.assertEqual(result['state'], 'unresolved')
        self.scope.assert_not_called()
        self.loader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
