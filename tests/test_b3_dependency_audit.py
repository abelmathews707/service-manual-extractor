"""Authored one-hop dependency inspection; no real manual text or approvals."""

import hashlib
import unittest
from unittest.mock import Mock, patch

from acceptance.b3_dependency_audit import audit
from sme.contract import ContractError


class DependencyAuditTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            'start': b'<html><body><h1>Start</h1><a href="target.htm#next">Next</a>'
                     b'<a href="target.htm#missing">Other fragment</a></body></html>',
            'target': b'<html><body><h1>Target</h1><p>CAUTION: authored fixture only.</p>'
                      b'<a name="next"></a><table><tr><th colspan="2">Mode</th></tr>'
                      b'<tr><td>Alpha</td><td>2 V</td></tr></table>'
                      b'<a href="later.htm">Later</a><a href="start.htm">Return</a>'
                      b'<img src="diagram.png" alt="Authored diagram"></body></html>',
            'later': b'<html><body>Must not be loaded</body></html>'}
        self.evidence = {'units': [{'id': key, 'kind': 'section', 'citation': {
            'kind': 'path', 'path': 'originals/' + key + '.htm'},
            'original_sha256': hashlib.sha256(value).hexdigest()}
            for key, value in self.data.items()]}
        self.eligible = dict.fromkeys(self.data, 'confirmed')
        self.loader = Mock(side_effect=lambda unit: self.data[unit['id']])

    def run_audit(self, **kwargs):
        return audit('start', self.evidence, self.eligible, self.loader, **kwargs)

    def test_one_hop_deduplicates_and_retains_text_table_assets_without_following(self):
        report = self.run_audit()
        self.assertEqual([c.args[0]['id'] for c in self.loader.call_args_list], ['start', 'target'])
        self.assertEqual(report['original_loads'], ['start', 'target'])
        self.assertEqual([r['fragment_state'] for r in report['direct_references']],
                         ['present', 'missing'])
        target = report['documents'][1]
        self.assertIn('CAUTION:', target['page']['text'])
        self.assertIn('colspan', str(target['page']['structure']))
        self.assertEqual(len(target['page']['figures']), 1)
        self.assertEqual(len(target['downstream']), 2)
        self.assertEqual(report['recursive_original_loads'], 0)
        self.assertEqual(report['asset_loads'], 0)
        self.assertEqual(report['quality_approvals'], 0)
        self.assertEqual(report['association_approvals'], 0)
        self.assertFalse(report['diagnostic_ready'])

    def test_wrong_source_scope_loads_nothing(self):
        for state in ('possible', 'excluded', 'reference_only', 'unreviewed'):
            self.eligible['start'] = state
            with self.assertRaises(ContractError):
                self.run_audit()
        self.loader.assert_not_called()

    def test_wrong_destination_scope_loads_source_only(self):
        for state in ('possible', 'excluded', 'reference_only', 'unreviewed'):
            self.loader.reset_mock()
            self.eligible['target'] = state
            report = self.run_audit()
            self.assertEqual(report['original_loads'], ['start'])
            self.assertTrue(all(not r['original_loaded'] for r in report['direct_references']))
            self.assertEqual([c.args[0]['id'] for c in self.loader.call_args_list], ['start'])

    def test_changed_original_is_rejected_before_parsing(self):
        self.data['start'] += b'changed'
        with patch('acceptance.b3_dependency_audit.parse_html') as parser:
            with self.assertRaisesRegex(ContractError, 'hash changed'):
                self.run_audit()
            parser.assert_not_called()

    def test_changed_destination_stops_without_downstream_reads(self):
        self.data['target'] += b'changed'
        with self.assertRaisesRegex(ContractError, 'hash changed'):
            self.run_audit()
        self.assertEqual([c.args[0]['id'] for c in self.loader.call_args_list], ['start', 'target'])

    def test_budget_stops_before_destination_reads(self):
        with self.assertRaisesRegex(ContractError, 'budget'):
            self.run_audit(max_targets=0)
        self.assertEqual([c.args[0]['id'] for c in self.loader.call_args_list], ['start'])

    def test_missing_destination_metadata_remains_unresolved(self):
        self.evidence['units'] = [self.evidence['units'][0]]
        report = self.run_audit()
        self.assertEqual(report['original_loads'], ['start'])
        self.assertTrue(all(r['scope'] == 'unresolved' for r in report['direct_references']))
