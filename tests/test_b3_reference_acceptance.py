"""Authored review receipts only; these tests do not approve real manual content."""

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_structured_contracts import TIMESTAMP, fixtures

from acceptance.b3_review_reference import reviewed_logs, run
from sme.continuation_review import CHECKS, append_continuation_event, bind_continuation
from sme.continuation_review import new_continuation_review as new_review
from sme.contract import ContractError
from sme.structured_contracts import dependency_bindings, quality_state, seal_records


class VisualReferenceAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pdf = Path(self.temp.name) / 'authored.pdf'
        # Only a hash-bound witness fixture, not a claim of real PDF rendering.
        self.pdf.write_bytes(b'authored visual-review input')
        vocab, _, bundle, _ = fixtures()
        self.vocabulary = vocab
        records = copy.deepcopy(bundle['records'])
        for record in records:
            record['completeness'] = {'state': 'incomplete', 'missing': ['Authored missing path']}
        bundle = seal_records(records)
        self.bundles = {'source': bundle, 'target': bundle}
        source = next(r for r in bundle['records'] if r['type'] == 'procedure_step')
        target = next(r for r in bundle['records'] if r['type'] == 'diagnostic_node')
        binding = bind_continuation(source, target, reference=source['original_text'],
                                    configuration_ids=[vocab['configurations'][0]['id']])
        empty = new_review()
        self.proposal = append_continuation_event(
            empty, binding, action='propose', reviewer={'id': 'authored', 'kind': 'agent'},
            timestamp=TIMESTAMP, reason='Authored candidate', checks=dict.fromkeys(CHECKS, False),
            expected_revision=empty['revision'])
        checks = {'original_compared': True, 'values_and_units': True, 'qualifiers': True,
                  'context_complete': False, 'branches_complete': False, 'source_resolves': True}
        self.witness = {'contract': 'b3-visual-reference-review/v1',
                        'proposal_revision': self.proposal['revision'], 'timestamp': TIMESTAMP,
                        'reviewer': {'id': 'authored', 'kind': 'agent'},
                        'reason': 'Authored incomplete reference, not instructions',
                        'link_checks': dict.fromkeys(CHECKS, True), 'endpoints': {}}
        for name, record in (('source', source), ('target', target)):
            self.witness['endpoints'][name] = {
                'bundle_revision': bundle['revision'],
                'reviewed_dependencies': dependency_bindings(record['id'], bundle['records']),
                'pdf_path': str(self.pdf),
                'pdf_sha256': hashlib.sha256(self.pdf.read_bytes()).hexdigest(),
                'pages_reviewed': [1, 2], 'checks': checks.copy()}

    def run_review(self):
        return reviewed_logs(self.bundles, self.proposal, self.witness)

    def test_review_preserves_proposal_and_only_approves_partial_engineering_reference(self):
        original = copy.deepcopy(self.proposal)
        quality, approved = self.run_review()
        self.assertEqual(self.proposal, original)
        self.assertEqual(approved['events'][:-1], original['events'])
        self.assertEqual(approved['events'][-1]['action'], 'approve')
        for name, overlay in quality.items():
            records = self.bundles[name]['records']
            identifier = overlay['events'][-1]['record_id']
            self.assertTrue(quality_state(identifier, records, overlay,
                                           intended_use='readable_reference',
                                           purpose='engineering')['approved'])
            for use, purpose in (('diagnostic_instruction', 'engineering'),
                                  ('structured_reference', 'engineering'),
                                  ('readable_reference', 'production')):
                self.assertFalse(quality_state(identifier, records, overlay,
                                                intended_use=use, purpose=purpose)['approved'])

    def test_pdf_mutation_invalidates_review(self):
        self.pdf.write_bytes(b'changed input')
        with self.assertRaisesRegex(ContractError, 'PDF bytes changed'):
            self.run_review()

    def test_omitted_dependency_and_wrong_bundle_revision_fail(self):
        endpoint = self.witness['endpoints']['target']
        original = copy.deepcopy(endpoint)
        endpoint['reviewed_dependencies'].pop()
        with self.assertRaisesRegex(ContractError, 'dependency'):
            self.run_review()
        self.witness['endpoints']['target'] = original
        original['bundle_revision'] = 'f' * 64
        with self.assertRaisesRegex(ContractError, 'revision'):
            self.run_review()

    def test_failed_checks_cannot_be_turned_into_approval(self):
        for name in CHECKS:
            self.witness['link_checks'][name] = False
            with self.assertRaisesRegex(ContractError, 'explicit visual review'):
                self.run_review()
            self.witness['link_checks'][name] = True
        checks = self.witness['endpoints']['target']['checks']
        for field in checks:
            original = checks[field]
            checks[field] = not original
            with self.assertRaisesRegex(ContractError, 'partial benchmark'):
                self.run_review()
            checks[field] = original

    def test_missing_invalid_or_duplicated_pages_fail(self):
        for pages in ([], [0], [True], [1, 1], [2, 1], '1'):
            self.witness['endpoints']['source']['pages_reviewed'] = pages
            with self.assertRaisesRegex(ContractError, 'PDF pages'):
                self.run_review()

    def test_changed_endpoint_or_dependency_is_not_reviewed(self):
        records = copy.deepcopy(self.bundles['target']['records'])
        records[0]['conditions'].append('additional authored condition')
        self.bundles['target'] = seal_records(records)
        with self.assertRaises(ContractError):
            self.run_review()

    def test_stale_proposal_and_backdating_fail(self):
        revision = self.witness['proposal_revision']
        self.witness['proposal_revision'] = 'f' * 64
        with self.assertRaisesRegex(ContractError, 'current proposal'):
            self.run_review()
        self.witness['proposal_revision'] = revision
        self.witness['timestamp'] = '2026-09-27T00:00:00+00:00'
        with self.assertRaisesRegex(ContractError, 'predate'):
            self.run_review()

    def test_unconfirmed_scope_stops_before_any_original_or_output(self):
        binding = self.proposal['events'][-1]['binding']
        report = {'binding': binding, 'source_unit_id': binding['source']['unit_id'],
                  'target_unit_id': binding['target']['unit_id']}
        inputs = {'link-candidate-verification.json': report,
                  'continuation-review.json': self.proposal,
                  'vocabulary.json': self.vocabulary, 'review.json': {'revision': 'review'}}
        root = Path(self.temp.name)
        for state in ('possible', 'excluded', 'unreviewed'):
            index = {'scopes': {'scope': {'scope': {'eligible': [
                {'unit_id': report['target_unit_id'], 'state': state}]}}}}
            with patch('acceptance.b3_review_reference.read',
                       side_effect=lambda path: inputs[path.name]), \
                    patch('acceptance.b3_review_reference.open_current',
                          return_value=(root, index)), \
                    patch('acceptance.b3_review_reference.search_export',
                          return_value={'fingerprint': 'scope'}), \
                    patch.object(Path, 'read_bytes') as original:
                with self.assertRaisesRegex(ContractError, 'current confirmed scope'):
                    run(root, root, self.witness, root / 'output')
                original.assert_not_called()
            self.assertFalse((root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
