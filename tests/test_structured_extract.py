"""Authored B2 layout/numeric/vehicle-boundary examples; no manual quotations."""

import copy
import unittest
from unittest.mock import patch

from test_structured_contracts import fixtures

from sme.contract import ContractError
from sme.structured_contracts import new_quality_overlay, quality_state, validate_records
from sme.structured_extract import (
    extract_html,
    extract_native_line,
    extract_part_mentions,
    numeric_value,
)

HTML = b'''<html><body><p>NOTE: Example measurements under fixture load.</p>
<table><caption>Example reference table</caption><tr>
<th rowspan=2>Signal</th><th colspan=2>Measured values</th><th rowspan=2>Units</th></tr>
<tr><th>Cold</th><th>Warm</th></tr>
<tr><td>DEMO</td><td>0</td><td>2-4</td><td>V</td></tr></table></body></html>'''
RECIPE = {'name': 'authored voltage', 'headers': [['Signal'], ['Measured values', 'Cold'],
           ['Measured values', 'Warm'], ['Units']], 'rows': ['DEMO'], 'unit_column': 3,
          'value_columns': [(1, 'Cold'), (2, 'Warm')], 'caption': 'Example reference table',
          'note': 'NOTE: Example measurements under fixture load.',
          'conditions': ['fixture load']}


class StructuredExtractionTests(unittest.TestCase):
    def setUp(self):
        self.vocabulary, self.evidence, bundle, _ = fixtures()
        self.binding = bundle['records'][0]['binding']
        self.config = self.vocabulary['configurations'][0]['id']
        self.decisions = {self.config: {'state': 'confirmed', 'configuration_id': self.config,
                                       'unit_id': self.binding['unit_id']}}

    def html(self, data=HTML, recipe=None):
        return extract_html(data, self.binding, self.vocabulary, [self.config],
                            self.decisions, [recipe or RECIPE])

    def test_merged_headers_zero_range_context_and_no_approval(self):
        bundle, errors = self.html()
        self.assertEqual(errors, [])
        record = next(item for item in bundle['records'] if item['type'] == 'specification')
        self.assertEqual(record['conditions'], ['Cold', 'Warm', 'fixture load'])
        self.assertEqual(record['payload']['values'][0]['normalized']['minimum'], 0)
        self.assertEqual(record['payload']['values'][1]['normalized']['maximum'], 4)
        self.assertEqual(record['payload']['values'][1]['original_value'], '2-4')
        self.assertEqual(len(record['context_record_ids']), 3)
        self.assertIn('table:nth-of-type(1) > tr:nth-of-type(3)', record['locator']['selector'])
        texts = {self.binding['unit_id']: ' '.join(item['original_text']
                                                 for item in bundle['records'])}
        validate_records(bundle, self.vocabulary, [self.evidence], source_texts=texts)
        self.assertFalse(quality_state(record['id'], bundle['records'], new_quality_overlay(),
                                       intended_use='structured_reference')['approved'])

    def test_missing_is_not_zero_composite_and_footnotes_are_ambiguous(self):
        for raw in (b'?', b'2/4', b'2-4 (A)', b'NaN', b'4-2'):
            bundle, _ = self.html(HTML.replace(b'2-4', raw))
            record = next(item for item in bundle['records'] if item['type'] == 'specification')
            self.assertEqual(record['completeness']['state'], 'ambiguous')
            self.assertNotIn('normalized', record['payload']['values'][1])
        bundle, errors = self.html(HTML.replace(b'<td>0</td><td>2-4</td>', b'<td></td><td></td>'))
        self.assertFalse(any(item['type'] == 'specification' for item in bundle['records']))
        self.assertIn('no readable values', errors[0]['reason'])

    def test_headers_conditions_nested_tables_and_duplicate_rows_fail_closed(self):
        changed = copy.deepcopy(RECIPE)
        changed['value_columns'][0] = (1, 'Warm')
        with self.assertRaises(ContractError):
            self.html(recipe=changed)
        for data in (HTML.replace(b'<th>Cold</th>', b'<th>Hot</th>'),
                     HTML.replace(b'<td>DEMO</td>', b'<td><table></table>DEMO</td>'),
                     HTML.replace(b'</table>', b'<tr><td>DEMO</td><td>1</td>'
                                  b'<td>3</td><td>V</td></tr></table>')):
            bundle, errors = self.html(data)
            self.assertFalse(any(item['type'] == 'specification' for item in bundle['records']))
            self.assertTrue(errors)

    def test_note_cannot_leak_from_previous_table(self):
        data = HTML.replace(b'<table><caption>', b'<table><tr><td>Other</td></tr></table>'
                            b'<table><caption>')
        bundle, errors = self.html(data)
        self.assertFalse(bundle['records'])
        self.assertIn('context', errors[0]['reason'])

    def test_wrong_vehicle_rejected_before_parser_or_text_loading(self):
        for change in ({'state': 'excluded'}, {'unit_id': 'different'},
                       {'configuration_id': 'different'}):
            self.decisions[self.config].update(change)
            with patch('sme.structured_extract.TreeParser') as parser:
                with self.assertRaises(ContractError):
                    self.html()
                parser.assert_not_called()

    def test_ocr_rows_abstain_and_missing_units_do_not_guess(self):
        self.binding['provenance'] = 'ocr'
        self.assertFalse(self.html()[0]['records'])
        self.binding['provenance'] = 'native'
        bundle, _ = self.html(HTML.replace(b'<td>V</td>', b'<td>unknown</td>'))
        record = next(item for item in bundle['records'] if item['type'] == 'specification')
        self.assertEqual(record['completeness']['state'], 'ambiguous')

    def test_parts_keep_namespace_and_only_mention_never_fitment(self):
        for namespace in ('authored manufacturer A', 'authored manufacturer B'):
            bundle, _ = extract_part_mentions('Example sealant DEMO-123.', self.binding,
                                              self.vocabulary, [self.config], self.decisions,
                                              pattern=r'DEMO-\d+', namespace=namespace)
            payload = bundle['records'][0]['payload']
            self.assertEqual(payload, {'identifier_original': 'DEMO-123',
                                       'namespace': namespace, 'relationship': 'mentioned'})
        self.binding['provenance'] = 'ocr'
        bundle, errors = extract_part_mentions('DEMO-123', self.binding, self.vocabulary,
                                               [self.config], self.decisions,
                                               pattern=r'DEMO-\d+', namespace='authored')
        self.assertFalse(bundle['records'])
        self.assertTrue(errors)

    def test_native_pdf_region_grammar_and_illustration_abstention(self):
        pattern = r'(?P<subject>Example bolt) (?P<value>\d+-\d+) (?P<unit>N.m)'
        kwargs = {'locator': {'kind': 'pdf_region', 'page': 1, 'bbox': [0, 0, 1, 1]},
                  'pattern': pattern, 'condition': 'installation stage 1'}
        bundle, errors = extract_native_line('Example bolt 2-4 N.m', self.binding,
                                             self.vocabulary, [self.config],
                                             self.decisions, **kwargs)
        self.assertEqual(errors, [])
        self.assertEqual(bundle['records'][0]['payload']['values'][0]['normalized']['maximum'], 4)
        for text in ('Fig. 1: Example pressure 2-4 N.m', 'Example bolt 2-4/3-5 N.m',
                     'DO NOT proceed above 2-4 N.m'):
            bundle, errors = extract_native_line(text, self.binding, self.vocabulary,
                                                 [self.config], self.decisions, **kwargs)
            self.assertFalse(bundle['records'])
            self.assertTrue(errors)

    def test_numeric_precision_signed_ranges_and_units_are_not_converted(self):
        self.assertEqual(numeric_value('-2--1', 'V')['minimum'], -2)
        self.assertEqual(numeric_value('.001 to .002', 'in')['unit'], 'in')
        for raw, unit in [('2/4', 'V'), ('2e3', 'Hz'), ('?', 'V'), ('2', 'guess')]:
            self.assertIsNone(numeric_value(raw, unit))


if __name__ == '__main__':
    unittest.main()
