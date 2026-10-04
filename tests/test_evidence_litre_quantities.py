"""Authored examples: fluid thresholds must not become engine restrictions."""

import unittest

from sme.evidence import _ENGINE, _mixed, _new_unit


class LitreQuantityTests(unittest.TestCase):
    def test_decimal_token_is_never_a_suffix(self):
        for value in ('0.95', '12.75', '.95'):
            with self.subTest(value=value):
                self.assertEqual(_ENGINE.findall(value + ' liter'), [value])
        for value in ('105.25', '2004', '1,095'):
            self.assertEqual(_ENGINE.findall(value + ' L'), [])

    def test_explicit_oil_rate_and_quart_conversion_is_not_second_engine(self):
        text = '6.0L diesel. Oil consumption rate is not higher than 0.95 liter (1 quart).'
        self.assertFalse(_mixed(text))

    def test_existing_unit_spellings_keep_real_mixed_engines_blocked(self):
        for unit in ('L', 'liter', 'litre', 'l', 'LITRE'):
            with self.subTest(unit=unit):
                self.assertTrue(_mixed(f'6.0{unit} diesel and 5.4{unit} gasoline'))

    def test_oil_keyword_alone_does_not_suppress_engine(self):
        self.assertTrue(_mixed('6.0L diesel. Oil consumption diagnosis for the 5.4L engine.'))

    def test_comparison_without_quart_conversion_stays_ambiguous(self):
        self.assertTrue(_mixed('6.0L diesel. Oil consumption rate is higher than 0.95 litre.'))

    def test_conversion_without_oil_rate_stays_ambiguous(self):
        self.assertTrue(_mixed('6.0L diesel. Capacity 0.95 liter (1 quart).'))

    def test_conversion_does_not_hide_actual_other_engine(self):
        self.assertTrue(_mixed('6.0L diesel; 5.4L gasoline. '
                               'Oil consumption is higher than 0.95 liter (1 quart).'))

    def test_different_sentence_cannot_supply_oil_rate_context(self):
        self.assertTrue(_mixed('6.0L diesel. Oil consumption rate is higher than. '
                               '0.95 liter (1 quart) engine.'))

    def test_capture_state_changes_only_for_bounded_oil_rate_case(self):
        document = {'id': 'doc-test', 'content_sha256': 'a' * 64,
                    'citations': [{'kind': 'path', 'path': 'originals/example.htm'}]}
        content = {'text': '6.0L diesel. Oil consumption is higher than 0.95 liter (1 quart).'}
        unit = _new_unit('generation', document, content, 'section', 'document')
        self.assertFalse(unit['mixed_content'])
        self.assertEqual(unit['search']['state'], 'whole')
        content['text'] += ' 5.4L gasoline.'
        unit = _new_unit('generation', document, content, 'section', 'document')
        self.assertTrue(unit['mixed_content'])
        self.assertEqual(unit['search']['state'], 'metadata_only')


if __name__ == '__main__':
    unittest.main()
