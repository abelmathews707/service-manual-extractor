"""Authored decimal-order/tool recipes; never licensed source instructions."""

import copy
import unittest
from unittest.mock import patch

from test_structured_contracts import fixtures

from sme.contract import ContractError
from sme.html_content import TreeParser, parse_html
from sme.ordered_procedure import extract_html_ordered_steps
from sme.structured_contracts import validate_records
from sme.structured_extract import _selector

HTML = b'''<html><body><h2>Authored fixture check</h2>
<p>Fixture meter DEMO-123</p><ol start="1"><li>Connect the fixture.</li></ol>
<ol start="2"><li>Read the fixture.</li><li>Disconnect the fixture.</li></ol></body></html>'''


class OrderedProcedureTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary, self.evidence, bundle, _ = fixtures()
        self.binding = copy.deepcopy(bundle['records'][0]['binding'])
        self.config = self.vocabulary['configurations'][0]['id']
        self.decisions = {self.config: {'state': 'confirmed', 'configuration_id': self.config,
                                       'unit_id': self.binding['unit_id']}}

    def extract(self, data=HTML, **kwargs):
        parser = TreeParser()
        parser.feed(data.decode())
        parser.close()
        lists = [_selector(node) for node in parser.root.walk() if node.tag == 'ol' and
                 node.parent.tag == 'body']
        tool = next(_selector(node) for node in parser.root.walk() if node.tag == 'p')
        arguments = {'list_selectors': lists, 'required_tools': [(tool, 'Authored fixture check')],
                     'coverage_reviewed': True} | kwargs
        bundle = extract_html_ordered_steps(data, self.binding, self.vocabulary, [self.config],
                                            self.decisions, **arguments)
        validate_records(bundle, self.vocabulary, [self.evidence], source_texts={
            self.binding['unit_id']: ' '.join(parse_html(data, 'authored.html')['text'].split())})
        return bundle['records']

    def test_split_decimal_lists_preserve_steps_tool_and_linear_order(self):
        records = self.extract()
        steps = [r for r in records if r['type'] == 'procedure_step']
        tool = next(r for r in records if r['type'] == 'tool')
        self.assertEqual([r['payload']['sequence'] for r in steps], [1, 2, 3])
        self.assertEqual(tool['payload']['name'], 'Fixture meter DEMO-123')
        self.assertEqual(steps[0]['payload']['tool_ids'], [tool['id']])
        self.assertEqual(steps[0]['payload']['next_record_ids'], [steps[1]['id']])
        self.assertEqual(steps[-1]['payload']['next_record_ids'], [])
        self.assertTrue(all(r['completeness']['state'] == 'complete' for r in records))

    def test_unreviewed_context_never_claims_complete_sequence(self):
        steps = [r for r in self.extract(coverage_reviewed=False) if r['type'] == 'procedure_step']
        self.assertTrue(all(r['completeness']['state'] == 'incomplete' for r in steps))
        self.assertTrue(all(not r['payload']['next_record_ids'] for r in steps))

    def test_gaps_resets_reversals_and_li_value_changes_abstain(self):
        for data in (HTML.replace(b'start="2"', b'start="4"'),
                     HTML.replace(b'start="2"', b'start="1"'),
                     HTML.replace(b'start="1"', b'start="1" reversed'),
                     HTML.replace(b'<li>Read', b'<li value="9">Read'),
                     HTML.replace(b'<li>Read', b'<p>Unassigned</p><li>Read')):
            with self.assertRaises(ContractError):
                self.extract(data)

    def test_nested_and_conditional_alternatives_are_not_flattened(self):
        for content in (b'If fitted, read fixture; otherwise stop.',
                        b'Read fixture.<ol type="a"><li>Use alternate scale.</li></ol>',
                        b'Refer to <a href="next.html">next check</a>.'):
            records = self.extract(HTML.replace(b'Read the fixture.', content))
            steps = [r for r in records if r['type'] == 'procedure_step']
            self.assertEqual(len(steps), 3)
            self.assertTrue(all(r['completeness']['state'] == 'incomplete' for r in steps))
            self.assertTrue(all(not r['payload']['next_record_ids'] for r in steps))
            self.assertIn('fixture' if b'fixture' in content else 'next check',
                          steps[1]['original_text'])

    def test_other_engine_and_invented_tool_operation_are_rejected(self):
        with self.assertRaises(ContractError):
            self.extract(HTML.replace(b'Read the fixture.', b'For 6.0L gasoline, read fixture.'))
        with self.assertRaises(ContractError):
            self.extract(required_tools=[('html:nth-of-type(1)', 'Invented operation')])

    def test_recipe_cannot_reorder_or_duplicate_original_lists(self):
        base = 'html:nth-of-type(1) > body:nth-of-type(1) > '
        first, second = (base + f'ol:nth-of-type({n})' for n in (1, 2))
        for selectors in ([second, first], [first, first], [base + 'ol:nth-of-type(99)']):
            with self.assertRaises(ContractError):
                self.extract(list_selectors=selectors)

    def test_diagram_is_not_silently_lost_from_completeness(self):
        records = self.extract(HTML.replace(b'Read the fixture.',
                                           b'Read shown pins. <img src="pins.png">'))
        steps = [r for r in records if r['type'] == 'procedure_step']
        self.assertTrue(all(r['completeness']['state'] == 'incomplete' for r in steps))
        self.assertIn('Step figure/diagram requires bound context review',
                      steps[0]['completeness']['missing'])

    def test_scope_and_ocr_are_checked_before_parsing(self):
        for change in ('scope', 'ocr'):
            if change == 'scope':
                self.decisions[self.config]['state'] = 'excluded'
            else:
                self.decisions[self.config]['state'] = 'confirmed'
                self.binding['provenance'] = 'ocr'
            with patch('sme.ordered_procedure.TreeParser') as parser:
                with self.assertRaises(ContractError):
                    self.extract()
                parser.assert_not_called()


if __name__ == '__main__':
    unittest.main()
