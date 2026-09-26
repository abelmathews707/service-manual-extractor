"""Vocabulary binding must not invent fitment or cross-product vehicle lists."""

import unittest

from test_applicability_contracts import make_vocabulary

from sme.vehicle_interpretation import interpret_statement


class VehicleInterpretationTest(unittest.TestCase):
    def setUp(self):
        self.vocabulary = make_vocabulary()
        self.models = {item['name']: item['id'] for item in self.vocabulary['models']}
        self.engines = {item['name']: item['id'] for item in self.vocabulary['engines']}

    def test_structured_ford_vehicle_maps_only_known_tuple(self):
        alternatives, resolved = interpret_statement(
            '2003 F-250 6.0L', self.vocabulary,
            {'year': '2003', 'name': 'F-250', 'engine': '6.0L'})
        self.assertTrue(resolved)
        self.assertEqual(alternatives[0]['model']['value'], self.models['F-250'])
        self.assertEqual(alternatives[0]['engine']['value'], self.engines['6.0L diesel'])
        self.assertEqual(alternatives[0]['year'], {'state': 'exact', 'value': 2003})

    def test_article_title_still_needs_review_and_engine(self):
        alternatives, resolved = interpret_statement(
            '2006 Chevrolet Silverado 1500', self.vocabulary)
        self.assertTrue(resolved)
        self.assertEqual(alternatives[0]['model']['value'], self.models['Silverado 1500'])
        self.assertEqual(alternatives[0]['engine'], {'state': 'unknown'})

    def test_copyright_year_is_not_model_year(self):
        alternatives, _ = interpret_statement('Copyright 2007', self.vocabulary)
        self.assertEqual(alternatives[0]['year'], {'state': 'unknown'})

    def test_conflicting_engine_never_makes_invalid_tuple(self):
        alternatives, resolved = interpret_statement(
            '2006 Chevrolet Silverado 1500 6.0L diesel', self.vocabulary)
        self.assertFalse(resolved)
        self.assertEqual(alternatives[0]['engine'], {'state': 'unknown'})

    def test_multiple_models_keep_owners_and_unknown_year(self):
        alternatives, resolved = interpret_statement(
            '2006 Chevrolet Silverado 1500 and 2003 Ford F-250', self.vocabulary)
        self.assertFalse(resolved)
        self.assertEqual({item['model']['value'] for item in alternatives},
                         {self.models['Silverado 1500'], self.models['F-250']})
        self.assertTrue(all(item['year']['state'] == 'unknown' for item in alternatives))

    def test_year_scoped_alias_does_not_leak_to_other_years(self):
        alternatives, resolved = interpret_statement('2004 F-Super Duty', self.vocabulary)
        self.assertEqual(alternatives[0]['model'], {'state': 'unknown'})
        self.assertTrue(resolved)


if __name__ == '__main__':
    unittest.main()
