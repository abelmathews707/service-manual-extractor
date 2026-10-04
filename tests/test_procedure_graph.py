"""Authored graph fixtures, never copied vehicle instructions."""

import copy
import unittest

from test_structured_contracts import CHECKS, TIMESTAMP, fixtures

from sme.contract import ContractError
from sme.procedure_graph import graph_completeness
from sme.structured_contracts import append_quality_event, new_quality_overlay, seal_records


class ProcedureGraphTests(unittest.TestCase):
    def setUp(self):
        _, _, bundle, _ = fixtures()
        self.records = copy.deepcopy(bundle['records'])
        self.decision = next(r for r in self.records
                             if r['payload'].get('node_kind') == 'decision')
        self.edges = [r for r in self.records if r['type'] == 'diagnostic_edge']

    def audit(self, root=None):
        return graph_completeness(root or self.decision['id'],
                                  seal_records(self.records)['records'])

    def test_complete_branches_preserve_bindings_but_never_grant_approval(self):
        before = copy.deepcopy(self.records)
        report = self.audit()
        self.assertEqual(report['state'], 'complete')
        self.assertEqual(report['flow_records'], 3)
        self.assertEqual(report['flow_edges'], 2)
        self.assertEqual(len(report['terminal_record_ids']), 2)
        self.assertFalse(report['diagnostic_ready'])
        self.assertEqual(before, self.records)

    def test_missing_branch_is_incomplete_even_when_node_claims_complete(self):
        self.records.remove(self.edges[-1])
        self.assertEqual(self.audit()['state'], 'incomplete')

    def test_closed_cycle_cannot_masquerade_as_complete_instructions(self):
        for edge in self.edges:
            edge['payload']['to_record_id'] = self.decision['id']
        report = self.audit()
        self.assertEqual(report['state'], 'incomplete')
        self.assertEqual(report['terminal_record_ids'], [])
        self.assertIn('No explicit terminal', report['problems'][0]['reason'])

    def test_repeat_with_explicit_exit_is_retained_not_executed(self):
        self.edges[0]['payload']['to_record_id'] = self.decision['id']
        report = self.audit()
        self.assertEqual(report['state'], 'complete')
        self.assertEqual(report['flow_edges'], 2)
        self.assertEqual(len(report['terminal_record_ids']), 1)

    def test_incomplete_terminal_is_not_hidden_by_complete_parent(self):
        outcome = next(r for r in self.records if r['payload'].get('node_kind') == 'outcome')
        outcome['completeness'] = {'state': 'incomplete', 'missing': ['Unreviewed next page']}
        self.assertEqual(self.audit()['problems'], [
            {'record_id': outcome['id'], 'reason': 'Unreviewed next page'}])

    def test_incomplete_warning_or_tool_blocks_procedure_closure(self):
        step = next(r for r in self.records if r['type'] == 'procedure_step')
        tool = next(r for r in self.records if r['type'] == 'tool')
        tool['completeness'] = {'state': 'incomplete', 'missing': ['Tool range not reviewed']}
        self.assertEqual(self.audit(step['id'])['state'], 'incomplete')

    def test_unrelated_incomplete_record_does_not_poison_selected_graph(self):
        part = next(r for r in self.records if r['type'] == 'part_reference')
        part['completeness'] = {'state': 'incomplete', 'missing': ['Unrelated part ambiguity']}
        self.assertEqual(self.audit()['state'], 'complete')

    def test_wrong_hash_missing_target_and_duplicate_records_rejected(self):
        changed = copy.deepcopy(self.records)
        changed[0]['payload']['instruction'] += ' mutation'
        with self.assertRaises(ContractError):
            graph_completeness(changed[0]['id'], changed)
        with self.assertRaises(ContractError):
            graph_completeness(self.decision['id'], self.records + [self.decision])
        self.edges[0]['payload']['to_record_id'] = 'record_' + 'a' * 32
        with self.assertRaises(ContractError):
            self.audit()

    def test_quality_gate_rejects_closed_cycle_but_allows_reference_reading(self):
        for edge in self.edges:
            edge['payload']['to_record_id'] = self.decision['id']
        records = seal_records(self.records)['records']
        for intended_use in ('readable_reference', 'structured_reference',
                             'diagnostic_instruction'):
            arguments = {'record_id': self.decision['id'], 'intended_use': intended_use,
                         'purpose': 'engineering', 'reviewer': {'id': 'authored', 'kind': 'agent'},
                         'timestamp': TIMESTAMP, 'reason': 'Authored regression fixture',
                         'checks': CHECKS}
            proposed = append_quality_event(new_quality_overlay(), records, action='propose',
                                             **arguments)
            if intended_use == 'readable_reference':
                append_quality_event(proposed, records, action='approve', **arguments,
                                     prior_event_id=proposed['events'][-1]['id'])
            else:
                with self.assertRaisesRegex(ContractError, 'complete bounded graph'):
                    append_quality_event(proposed, records, action='approve', **arguments,
                                         prior_event_id=proposed['events'][-1]['id'])


if __name__ == '__main__':
    unittest.main()
