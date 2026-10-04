"""Authored publication checks: reject disallowed shards before reading bytes."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from acceptance.b3_publish_candidate import FORD, run, verify_scopes
from sme.contract import ContractError


class CandidatePublicationTests(unittest.TestCase):
    def setUp(self):
        self.configs = {name: {'id': name} for name in ('diesel', 'gm-w', 'v10', 'cng')}
        self.snapshots = [{'source_id': FORD, 'units': [{'id': 'chart'}]},
                          {'source_id': 'gm', 'units': [{'id': 'gm-page'}]}]
        self.index = {'scopes': {name: {'scope': {'eligible': [
            {'unit_id': unit} for unit in units]}}
            for name, units in [('diesel', ['chart']), ('gm-w', ['gm-page']),
                                ('v10', []), ('cng', [])]},
            'shards': {'ford': {'path': 'shards/ford.json', 'unit_ids': ['chart']},
                       'gm': {'path': 'shards/gm.json', 'unit_ids': ['gm-page']}}}
        self.requests = {'diesel': ['ford'], 'gm-w': ['gm'], 'v10': [], 'cng': []}
        self.stage = Path('/authored-candidate-no-files')

    def verify(self):
        def search(stage, index, selection, query, **kwargs):
            name = selection['id']
            shards = self.requests[name] if query else []
            for shard in shards:
                kwargs['load_shard'](self.stage / index['shards'][shard]['path'])
            return {'fingerprint': name, 'loaded_shard_ids': shards}

        with patch('acceptance.b3_publish_candidate._configs', return_value=self.configs), \
                patch('acceptance.b3_publish_candidate._selection', side_effect=lambda c: c), \
                patch('acceptance.b3_publish_candidate.search_export', side_effect=search):
            return verify_scopes(str(self.stage), self.index, {}, {'revision': 'authored'},
                                 'chart', self.snapshots)

    def test_audits_actual_allowed_reads_without_mutating_metadata(self):
        before = copy.deepcopy(self.index)
        with patch('acceptance.b3_publish_candidate.read', return_value=[]) as read:
            checks = self.verify()
        self.assertEqual(read.call_count, 2)
        self.assertEqual(checks['diesel']['actual_shard_reads'], ['shards/ford.json'])
        self.assertEqual(checks['gm-w']['actual_shard_reads'], ['shards/gm.json'])
        self.assertEqual(checks['v10']['actual_shard_reads'], [])
        self.assertEqual(before, self.index)

    def test_ford_request_for_gm_fails_before_bytes_are_read(self):
        self.requests['diesel'] = ['gm']
        with patch('acceptance.b3_publish_candidate.read') as read:
            with self.assertRaisesRegex(ContractError, 'excluded text shard requested'):
                self.verify()
            read.assert_not_called()

    def test_same_brand_but_ineligible_unit_also_fails_before_read(self):
        self.index['shards']['ford']['unit_ids'].append('unapproved-ford-page')
        with patch('acceptance.b3_publish_candidate.read') as read:
            with self.assertRaises(ContractError):
                self.verify()
            read.assert_not_called()

    def test_mixed_shard_cannot_hide_gm_content_behind_ford_membership(self):
        self.index['shards']['ford']['unit_ids'].append('gm-page')
        self.index['scopes']['diesel']['scope']['eligible'].append({'unit_id': 'gm-page'})
        with patch('acceptance.b3_publish_candidate.read') as read:
            with self.assertRaises(ContractError):
                self.verify()
            read.assert_not_called()

    def test_wrong_engine_chart_admission_rejected(self):
        self.configs = {'v10': self.configs['v10']}
        self.index['scopes']['v10']['scope']['eligible'] = [{'unit_id': 'chart'}]
        with patch('acceptance.b3_publish_candidate.read') as read:
            with self.assertRaisesRegex(ContractError, 'eligibility regression'):
                self.verify()
            read.assert_not_called()

    def test_lost_diesel_chart_rejected(self):
        self.index['scopes']['diesel']['scope']['eligible'] = []
        with patch('acceptance.b3_publish_candidate.read') as read:
            with self.assertRaisesRegex(ContractError, 'eligibility regression'):
                self.verify()
            read.assert_not_called()

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('acceptance.b3_publish_candidate.read') as read:
                with self.assertRaisesRegex(ContractError, 'new output directory'):
                    run(Path('/unused'), Path('/unused'), Path(temporary))
                read.assert_not_called()


if __name__ == '__main__':
    unittest.main()
