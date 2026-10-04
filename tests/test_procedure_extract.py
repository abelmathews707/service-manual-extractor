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
    extract_html_decisions,
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

    def test_context_references_are_inventoried_without_losing_note(self):
        data = HTML.replace(b'<div class="question">',
                            b'<ul><p>If unavailable, refer to <a href="setup.htm">setup</a>.</p>'
                            b'<li>Read <a href="tool.htm">tool instructions</a>.</li></ul>'
                            b'<div class="question">')
        bundle, links = self.html(data)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]['label'], 'context')
        self.assertEqual(links[0]['targets'], ['setup.htm', 'tool.htm'])
        owner = next(r for r in bundle['records'] if r['id'] == links[0]['record_id'])
        self.assertIn('If unavailable, refer to setup.', owner['original_text'])
        self.assertEqual(links[0]['state'], 'unresolved')

    def multiple(self, data, anchors=('test1', 'test2')):
        bundle, inventory = extract_html_decisions(
            data, self.binding, self.vocabulary, [self.config], self.decisions, anchors=anchors,
            missing_context=['Authored prerequisite not reviewed'])
        validate_records(bundle, self.vocabulary, [self.evidence], source_texts={
            self.binding['unit_id']: ' '.join(parse_html(data, 'authored.html')['text'].split())})
        return bundle, inventory

    def test_multiple_sections_keep_distinct_questions_and_all_branches(self):
        first = HTML.replace(b'Record absent.', b'Go to <a href="#test2">second</a>.')
        second = HTML.replace(b'name="test1"', b'id="test2"').replace(
            b'Is the signal present?', b'Is the fixture ready?')
        data = first.replace(b'</body></html>', b'') + second.replace(b'<html><body>', b'')
        bundle, inventory = self.multiple(data)
        decisions = [r for r in bundle['records'] if r['payload'].get('node_kind') == 'decision']
        self.assertEqual([r['original_text'] for r in decisions],
                         ['Is the signal present?', 'Is the fixture ready?'])
        self.assertEqual(len([r for r in bundle['records'] if r['type'] == 'diagnostic_edge']), 4)
        link = inventory['references'][0]
        self.assertEqual(link['candidates'][0]['record_id'], decisions[1]['id'])
        self.assertEqual(link['state'], 'unresolved')
        self.assertFalse(inventory['diagnostic_ready'])
        self.assertTrue(all(r['completeness']['state'] == 'incomplete' for r in decisions))
        # Source-anchor candidates never introduce execution edges between sections.
        self.assertFalse(any(r['type'] == 'diagnostic_edge' and
                             r['payload']['to_record_id'] == decisions[1]['id']
                             for r in bundle['records']))

    def test_external_similar_and_unselected_targets_are_not_local_candidates(self):
        filename = self.binding['citation']['path'].rsplit('/', 1)[-1]
        for href, matches in ((filename + '#test1', True), ('#test1', True),
                              ('#missing', False), ('other.htm#test1', False),
                              ('https://example.invalid/' + filename + '#test1', False),
                              (filename + '?version=other#test1', False),
                              ('../' + filename + '#test1', False), ('http://[bad', False)):
            data = HTML.replace(b'Record absent.', ('See <a href="' + href +
                                                   '">reference</a>.').encode())
            _, inventory = self.multiple(data, anchors=['test1'])
            self.assertEqual(bool(inventory['references'][0]['candidates'][0]['record_id']),
                             matches, href)

    def test_multiple_sections_fail_closed_on_missing_or_duplicate_selection(self):
        for anchors in ([], ['test1', 'test1'], ['test1', 'missing'], [''], 'test1'):
            with self.assertRaises(ContractError):
                self.multiple(HTML, anchors=anchors)

    def test_multiple_sections_check_scope_before_parsing(self):
        self.decisions[self.config]['state'] = 'excluded'
        with patch('sme.procedure_extract.TreeParser') as parser:
            with self.assertRaises(ContractError):
                self.multiple(HTML)
            parser.assert_not_called()

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
