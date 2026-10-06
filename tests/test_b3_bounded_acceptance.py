"""Bounded acceptance must not mean diagnostic completeness or relaxed review."""

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_structured_contracts import fixtures

from acceptance.b3_bounded_acceptance import run, verify_bundle
from sme.contract import ContractError
from sme.structured_contracts import seal_records


class BoundedAcceptanceTests(unittest.TestCase):
    def setUp(self):
        _, _, bundle, _ = fixtures()
        records = bundle['records']
        for record in records:
            if record['type'] in ('procedure_step', 'diagnostic_node', 'diagnostic_edge'):
                record['completeness'] = {'state': 'incomplete',
                                           'missing': ['Authored external prerequisite']}
        self.bundle = seal_records(records)

    def test_pass_preserves_incomplete_graphs_and_blocks_every_instruction_promotion(self):
        before = copy.deepcopy(self.bundle)
        report = verify_bundle(self.bundle, self.bundle)
        self.assertEqual(len(report['instruction_promotions_blocked']), 6)
        self.assertTrue(all(g['state'] == 'incomplete' for g in report['graphs']))
        self.assertFalse(report['diagnostic_ready'])
        self.assertEqual(report['persisted_quality_events_added'], 0)
        self.assertEqual(before, self.bundle)

    def test_changed_wording_or_missing_branch_fails_frozen_comparison(self):
        records = copy.deepcopy(self.bundle['records'])
        records[-1]['conditions'].append('Unreviewed change')
        with self.assertRaises(ContractError):
            verify_bundle(seal_records(records), self.bundle)

    def test_new_extraction_version_is_reported_without_carrying_approval(self):
        records = copy.deepcopy(self.bundle['records'])
        records[0]['binding']['extraction_version'] = 'authored-new-parser'
        report = verify_bundle(seal_records(records), self.bundle)
        self.assertEqual(len(report['extraction_version_changes']), 1)
        self.assertEqual(report['persisted_quality_events_added'], 0)
        records[0]['binding']['evidence_revision'] = 'f' * 64
        with self.assertRaises(ContractError):
            verify_bundle(seal_records(records), self.bundle)
        records = [r for r in self.bundle['records'] if r['type'] != 'diagnostic_edge']
        with self.assertRaises(ContractError):
            verify_bundle(seal_records(records), self.bundle)

    def test_relabeling_incomplete_as_complete_is_not_bounded_acceptance(self):
        records = copy.deepcopy(self.bundle['records'])
        step = next(r for r in records if r['type'] == 'procedure_step')
        step['completeness'] = {'state': 'complete', 'missing': []}
        changed = seal_records(records)
        with self.assertRaisesRegex(ContractError, 'promoted to complete'):
            verify_bundle(changed, changed)

    def test_unexpected_error_cannot_masquerade_as_successful_quality_block(self):
        from sme.structured_contracts import append_quality_event

        def broken(*args, **kwargs):
            if kwargs['action'] == 'approve':
                raise ContractError('Unrelated validation failure')
            return append_quality_event(*args, **kwargs)

        with patch('acceptance.b3_bounded_acceptance.append_quality_event', side_effect=broken):
            with self.assertRaisesRegex(ContractError, 'Unrelated'):
                verify_bundle(self.bundle, self.bundle)

    def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ContractError, 'new output directory'):
                run(Path('/unused'), Path('/unused'), Path(directory))


if __name__ == '__main__':
    unittest.main()
