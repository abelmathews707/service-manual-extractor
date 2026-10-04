"""Authored metadata/transcription tests; no licensed manual content."""

import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import test_procedure_extract as procedure_fixture

from acceptance.b3_quick_test import compare, run, target_metadata
from sme.contract import ContractError


class QuickTestAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.citation = {'kind': 'path', 'path': 'originals/book/start.htm'}
        self.evidence = {'units': [
            {'kind': 'section', 'id': 'target',
             'citation': {'kind': 'path', 'path': 'originals/book/target.htm'}}]}

    def test_metadata_keeps_independent_scope_without_reading_targets(self):
        with patch.object(Path, 'read_bytes') as reader:
            for state in ('confirmed', 'possible', 'excluded'):
                result = target_metadata('target.htm#next', self.citation, self.evidence,
                                         {'target': state})
                self.assertEqual(result['scope'], state)
                self.assertEqual(result['fragment'], 'next')
                self.assertEqual(result['quality'], 'not_reviewed')
                self.assertFalse(result['original_loaded'])
            reader.assert_not_called()

    def test_missing_ambiguous_and_external_targets_stay_unresolved(self):
        for href in ('missing.htm', 'https://example.invalid/target.htm',
                     '../../../target.htm', 'target.htm?version=2', 'http://[broken',
                     '%74arget.htm', '..\\target.htm'):
            self.assertEqual(target_metadata(href, self.citation, self.evidence, {})[
                'scope'], 'unresolved')
        self.evidence['units'].append(copy.deepcopy(self.evidence['units'][0]))
        self.assertEqual(target_metadata('target.htm', self.citation, self.evidence, {})[
            'scope'], 'unresolved')

    def test_exact_comparison_detects_missing_context_branch_and_reference(self):
        fixture = procedure_fixture.ProcedureExtractionTests()
        fixture.setUp()
        bundle, inventory = fixture.multiple(procedure_fixture.HTML, anchors=['test1'])
        expected = {'sections': [{
            'anchor': 'test1', 'heading': 'Authored decision', 'context': [],
            'question': 'Is the signal present?',
            'branches': {'Yes': 'Record present.', 'No': 'Record absent.'}, 'references': []}]}
        compare(bundle, inventory, expected)
        for key, value in (('context', ['Lost prerequisite']),
                           ('branches', {'Yes': 'Record present.'}),
                           ('references', [{'label': 'context', 'targets': ['omitted.htm']}])):
            changed = copy.deepcopy(expected)
            changed['sections'][0][key] = value
            with self.assertRaises(ContractError):
                compare(bundle, inventory, changed)

    def test_unconfirmed_source_stops_before_pdf_or_html_reads(self):
        fixture = procedure_fixture.ProcedureExtractionTests()
        fixture.setUp()
        evidence = {'units': [{'kind': 'section', 'id': 'source', 'citation': {
            'kind': 'path', 'path': 'originals/content/useni4/v3d/V3D3001.htm'}}]}
        inputs = {'vocabulary.json': fixture.vocabulary, 'review.json': {'revision': 'review'}}
        for state in ('possible', 'excluded', 'unreviewed'):
            index = {'scopes': {'scope': {'scope': {'eligible': [
                {'unit_id': 'source', 'state': state}]}}}}
            with patch('acceptance.b3_quick_test.read',
                       side_effect=lambda path: inputs.get(path.name, evidence)), \
                    patch('acceptance.b3_quick_test._configs',
                          return_value={'diesel': fixture.vocabulary['configurations'][0]}), \
                    patch('acceptance.b3_quick_test.open_current', return_value=('/fake', index)), \
                    patch('acceptance.b3_quick_test.search_export',
                          return_value={'fingerprint': 'scope'}), \
                    patch.object(Path, 'read_bytes') as reader:
                with self.assertRaisesRegex(ContractError, 'before original reads'):
                    run(Path('/fake'), Path('/not-created'), {})
                reader.assert_not_called()
