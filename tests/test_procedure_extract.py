"""Authored structural examples; no licensed manual text."""

import copy
import unittest
from unittest.mock import patch

from test_structured_contracts import fixtures

from sme.contract import ContractError
from sme.html_content import parse_html
from sme.procedure_extract import (
    _covers_configurations,
    extract_html_decision,
    extract_native_decision,
)
from sme.structured_contracts import validate_records

HTML = b'''<html><body><a name="test1"></a><h4>Authored decision</h4>
<div class="question">Is the signal present?</div>
<table><tr><th>Yes</th><th>No</th></tr><tr><td>Record present.</td>
<td>Record absent.</td></tr></table></body></html>'''


class ProcedureExtractionTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary, self.evidence, bundle, _ = fixtures()
        self.binding = copy.deepcopy(bundle['records'][0]['binding'])
        self.config = self.vocabulary['configurations'][0]['id']
        self.decisions = {self.config: {'state': 'confirmed',
                                       'configuration_id': self.config,
                                       'unit_id': self.binding['unit_id']}}

    def html(self, data=HTML, **kwargs):
        bundle, links = extract_html_decision(data, self.binding, self.vocabulary,
                                              [self.config], self.decisions,
                                              anchor='test1', **kwargs)
        text = parse_html(data, 'authored.html')['text']
        validate_records(bundle, self.vocabulary, [self.evidence],
                         source_texts={self.binding['unit_id']: ' '.join(text.split())})
        return bundle, links

    def test_exact_both_branches_and_original_citations(self):
        bundle, links = self.html()
        self.assertEqual(links, [])
        edges = [r for r in bundle['records'] if r['type'] == 'diagnostic_edge']
        self.assertEqual([r['payload']['label'] for r in edges], ['Yes', 'No'])
        self.assertEqual([r['original_text'] for r in edges],
                         ['Record present.', 'Record absent.'])
        self.assertTrue(all(r['binding']['citation'] == self.binding['citation']
                            for r in bundle['records']))

    def test_missing_duplicate_or_merged_branches_abstain(self):
        for data in (HTML.replace(b'<th>No</th>', b'<th>Yes</th>'),
                     HTML.replace(b'<td>Record absent.</td>', b'<td></td>'),
                     HTML.replace(b'<td>Record present.</td>',
                                  b'<td colspan="2">Record present.</td>'),
                     HTML.replace(b'<a name="test1">',
                                  b'<a name="test1"></a><a name="test1">')):
            with self.assertRaises(ContractError):
                self.html(data)

    def test_cross_manual_links_remain_unresolved_and_never_fetched(self):
        data = HTML.replace(b'Record absent.', b'GO to <a href="other.htm#next">next</a>.')
        bundle, links = self.html(data)
        self.assertEqual(links[0]['targets'], ['other.htm#next'])
        decision = next(r for r in bundle['records']
                        if r.get('payload', {}).get('node_kind') == 'decision')
        self.assertEqual(decision['completeness']['state'], 'incomplete')

    def test_nested_notes_and_instruction_groups_are_retained(self):
        data = HTML.replace(b'<div class="question">',
                            b'<ul><li>Connect fixture.</li><p>Note: isolate supply.</p>'
                            b'<li>If configured, use adapter.</li></ul><div class="question">')
        bundle, _ = self.html(data)
        step = next(r for r in bundle['records'] if r['type'] == 'procedure_step')
        self.assertIn('Note: isolate supply.', step['payload']['instruction'])
        self.assertIn('If configured, use adapter.', step['payload']['instruction'])
        self.assertEqual(step['completeness']['state'], 'incomplete')

    def test_scope_checked_before_html_parse_and_ocr_abstains(self):
        self.decisions[self.config]['state'] = 'excluded'
        with patch('sme.procedure_extract.TreeParser') as parser:
            with self.assertRaises(ContractError):
                self.html()
            parser.assert_not_called()
        self.decisions[self.config]['state'] = 'confirmed'
        self.binding['provenance'] = 'ocr'
        with self.assertRaises(ContractError):
            self.html()

    def test_other_engine_in_branch_rejected(self):
        with self.assertRaises(ContractError):
            self.html(HTML.replace(b'Record absent.', b'For 6.0L gasoline record absent.'))
        with self.assertRaises(ContractError):
            self.html(HTML.replace(b'Is the signal present?', b'Is this a 6.0L gasoline signal?'))

    def test_fuel_only_context_narrows_confirmed_parent_without_guessing_engine(self):
        other = self.vocabulary['configurations'][1]['id']
        self.assertTrue(_covers_configurations('Diesel control system', self.vocabulary,
                                                [self.config]))
        for statement in ('Gasoline control system', 'Except diesel control systems',
                          'Not diesel', 'Diesel and gasoline', 'Diesel VIN unknown',
                          'Diesel is excluded', 'Other than diesel', 'Diesel unsupported',
                          'Diesel prohibited', 'Never diesel'):
            self.assertFalse(_covers_configurations(statement, self.vocabulary, [self.config]))
        self.assertFalse(_covers_configurations('Diesel control system', self.vocabulary,
                                                 [self.config, other]))

    def test_multi_configuration_procedure_cannot_keep_partial_engine_matches(self):
        other = self.vocabulary['configurations'][1]['id']
        decisions = self.decisions | {other: {'state': 'confirmed',
                                              'configuration_id': other,
                                              'unit_id': self.binding['unit_id']}}
        with self.assertRaises(ContractError):
            extract_html_decision(HTML.replace(b'Is the signal present?',
                                               b'Is the 6.0L diesel signal present?'),
                                  self.binding, self.vocabulary, [self.config, other], decisions,
                                  anchor='test1')

    def test_native_numbered_conditional_step_preserves_both_paths(self):
        text = '3. Read fixture meter. Is voltage below 4 V? If yes, go to next step. '
        text += 'If no, isolate fixture before proceeding.'
        bundle, links = extract_native_decision(
            text, self.binding, self.vocabulary, [self.config], self.decisions,
            locator={'kind': 'text_quote', 'quote': text, 'prefix': '', 'suffix': ''},
            missing_context=['prerequisite not reviewed'])
        validate_records(bundle, self.vocabulary, [self.evidence],
                         source_texts={self.binding['unit_id']: text})
        step = next(r for r in bundle['records'] if r['type'] == 'procedure_step')
        self.assertEqual(step['payload']['sequence'], 3)
        self.assertEqual(len(links), 2)
        self.assertTrue(all(r['completeness']['state'] == 'incomplete'
                            for r in bundle['records']))

    def test_native_missing_or_duplicate_branch_abstains(self):
        for text in ('1. Is signal present? If yes, stop.',
                     '1. Read meter. Is signal present? If yes, stop. If yes, repeat. If no, wait.',
                     '1. Is signal present? Is it stable? If yes, stop. If no, record absent.'):
            with self.assertRaises(ContractError):
                extract_native_decision(text, self.binding, self.vocabulary,
                                        [self.config], self.decisions,
                                        locator={'kind': 'pdf_region', 'page': 1,
                                                 'bbox': [0, 0, 1, 1]})


if __name__ == '__main__':
    unittest.main()
