"""A2 sidecar contract tests with authored vehicle/manual records only."""

import copy
import json
import os
import unittest

from sme.applicability_contracts import (
    EVIDENCE_CONTRACT,
    LIBRARY_CONTRACT,
    POLICY_VERSION,
    REASON_CODES,
    REVIEW_CONTRACT,
    SCOPE_CONTRACT,
    VOCABULARY_CONTRACT,
    assertion_digest,
    configuration_id,
    digest,
    evidence_revision,
    review_event_is_stale,
    scope_fingerprint,
    sidecar_id,
    unit_id,
    validate_evidence,
    validate_library,
    validate_review_overlay,
    validate_scope,
    validate_vocabulary,
)
from sme.contract import (
    ContractError,
    document_id,
    publication_id,
    source_id,
    validate_manifest,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZERO = '0' * 64
ONE = '1' * 64
TWO = '2' * 64
THREE = '3' * 64


def make_vocabulary():
    ford = sidecar_id('make', 'ford')
    chevrolet = sidecar_id('make', 'chevrolet')
    example = sidecar_id('make', 'example')
    f250 = sidecar_id('model', ford, 'f-250')
    silverado = sidecar_id('model', chevrolet, 'silverado-1500')
    citycar = sidecar_id('model', example, 'city-car')
    diesel = sidecar_id('engine', 'ford', '6-0-diesel')
    gasoline = sidecar_id('engine', 'gm', '6-0-gasoline')
    electric = sidecar_id('engine', 'example', 'electric')
    configs = [
        (ford, f250, 2003, diesel),
        (chevrolet, silverado, 2006, gasoline),
        (example, citycar, 2020, electric),
    ]
    vocabulary = {
        'contract': VOCABULARY_CONTRACT,
        'makes': [
            {'id': ford, 'key': 'ford', 'name': 'Ford'},
            {'id': chevrolet, 'key': 'chevrolet', 'name': 'Chevrolet'},
            {'id': example, 'key': 'example', 'name': 'Example'},
        ],
        'models': [
            {'id': f250, 'key': 'f-250', 'name': 'F-250', 'make_id': ford,
             'family': 'Super Duty'},
            {'id': silverado, 'key': 'silverado-1500', 'name': 'Silverado 1500',
             'make_id': chevrolet},
            {'id': citycar, 'key': 'city-car', 'name': 'City Car', 'make_id': example},
        ],
        'engines': [
            {'id': diesel, 'key': '6-0-diesel', 'name': '6.0L diesel',
             'manufacturer': 'ford', 'fuel': 'diesel', 'displacement_l': 6.0},
            {'id': gasoline, 'key': '6-0-gasoline', 'name': '6.0L gasoline',
             'manufacturer': 'gm', 'fuel': 'gasoline', 'displacement_l': 6.0},
            {'id': electric, 'key': 'electric', 'name': 'Electric motor',
             'manufacturer': 'example', 'fuel': 'electric', 'displacement_l': 0.1},
        ],
        'configurations': [
            {'id': configuration_id(make, model, year, engine), 'make_id': make,
             'model_id': model, 'model_year': year, 'engine_id': engine,
             'qualifiers': {}}
            for make, model, year, engine in configs
        ],
        'aliases': [{
            'literal': 'F-Super Duty', 'target_id': f250, 'make_id': ford,
            'year_start': 2003, 'year_end': 2003,
            'evidence': {'source_id': source_id('ford_tsp_disc_v1', 'disc',
                                             'authored-example', ZERO),
                         'citation': {'kind': 'path', 'path': 'catalog.txt'}},
        }],
    }
    vocabulary['revision'] = digest(vocabulary)
    return vocabulary


def make_manifest():
    source = {
        'id': source_id('workshop_manuals_html_v1', 'directory', 'authored/example', ZERO),
        'format': 'workshop_manuals_html_v1', 'container': 'directory',
        'identity': 'authored/example', 'sha256': ZERO, 'status': 'complete',
        'failures': [], 'extractor': {'name': 'test', 'version': '1', 'revision': 'synthetic'},
    }
    pub = publication_id(source['id'], 'index.html')
    doc = document_id(pub, 'pages/engine.html')
    return {
        'contract': 'service-manual-manifest/v1', 'source': source,
        'publications': [{
            'id': pub, 'source_path': 'index.html', 'title': 'Authored workshop',
            'kind': 'workshop', 'applicability': [],
            'documents': [{
                'id': doc, 'path': 'pages/engine.html', 'title': 'Engine table',
                'content_sha256': ONE, 'text': {'provenance': 'native', 'sha256': TWO},
                'citations': [{'kind': 'path', 'path': 'pages/engine.html'}],
                'applicability': [], 'references': [], 'assets': [],
            }],
        }],
    }


def exact(value):
    return {'state': 'exact', 'value': value}


def make_evidence(manifest, vocabulary):
    ford = vocabulary['makes'][0]['id']
    f250 = vocabulary['models'][0]['id']
    diesel = vocabulary['engines'][0]['id']
    doc = manifest['publications'][0]['documents'][0]
    generation = digest([digest(manifest), THREE])
    unit = {
        'id': unit_id(generation, doc['id'], 'table', '#engine-table'),
        'document_id': doc['id'], 'kind': 'table', 'selector': '#engine-table',
        'original_sha256': doc['content_sha256'],
        'citation': {'kind': 'path', 'path': doc['path']},
        'mixed_content': True,
        'search': {'state': 'metadata_only'},
    }
    assertion = {
        'subject_id': unit['id'], 'statement': '2003 F-250 6.0L diesel only',
        'citation': {'kind': 'path', 'path': doc['path']},
        'intent': 'include', 'applies_to_descendants': False,
        'derivation': 'explicit_text', 'provenance': 'native',
        'support': 'source_supported',
        'alternatives': [{
            'make': exact(ford), 'model': exact(f250), 'year': exact(2003),
            'engine': exact(diesel), 'qualifiers': {},
        }],
    }
    assertion['digest'] = assertion_digest(assertion)
    assertion['id'] = sidecar_id('ev', manifest['source']['id'], unit['id'],
                                 assertion['digest'])
    evidence = {
        'contract': EVIDENCE_CONTRACT,
        'source_id': manifest['source']['id'],
        'source_sha256': manifest['source']['sha256'],
        'manifest_sha256': digest(manifest),
        'content_sha256': THREE,
        'generation_sha256': generation,
        'vocabulary_revision': vocabulary['revision'],
        'units': [unit], 'assertions': [assertion],
    }
    evidence['revision'] = evidence_revision(evidence)
    return evidence


def make_review(evidence, vocabulary):
    assertion = evidence['assertions'][0]
    binding = {'id': assertion['id'], 'digest': assertion['digest']}
    config = vocabulary['configurations'][0]['id']
    shared = {
        'proposal_id': 'authored-review-1', 'subject_id': assertion['subject_id'],
        'relation': 'section_applies', 'target_configuration_ids': [config],
        'evidence_bindings': [binding], 'reviewer': 'example-reviewer',
        'timestamp': '2026-09-25T12:00:00Z', 'reason': 'Original page checked.',
        'source_id': evidence['source_id'],
        'evidence_revision': evidence['revision'],
        'vocabulary_revision': vocabulary['revision'],
        'policy_version': POLICY_VERSION,
    }
    proposal = {'action': 'propose', **shared}
    proposal['id'] = sidecar_id('review', digest(proposal))
    accepted = {'action': 'accept', **shared, 'prior_event_id': proposal['id']}
    accepted['id'] = sidecar_id('review', digest(accepted))
    review = {
        'contract': REVIEW_CONTRACT,
        'vocabulary_revision': vocabulary['revision'],
        'evidence_snapshots': [{'source_id': evidence['source_id'],
                                'revision': evidence['revision']}],
        'policy_version': POLICY_VERSION,
        'events': [proposal, accepted],
    }
    review['revision'] = digest(review)
    return review


def make_library(manifest, vocabulary, review):
    root = 'packages/authored-source'
    package = {
        'occurrence_id': sidecar_id('occ', manifest['source']['id'], root),
        'root': root, 'source_id': manifest['source']['id'],
        'manifest_sha256': digest(manifest), 'content_sha256': THREE,
        'status': 'active',
    }
    value = {
        'contract': LIBRARY_CONTRACT,
        'vocabulary_revision': vocabulary['revision'],
        'review_revision': review['revision'], 'policy_version': POLICY_VERSION,
        'packages': [package],
    }
    value['revision'] = digest(value)
    return value


def make_scope(library, vocabulary, unit):
    config = vocabulary['configurations'][0]
    value = {
        'contract': SCOPE_CONTRACT,
        'library_revision': library['revision'],
        'vocabulary_revision': vocabulary['revision'],
        'review_revision': library['review_revision'],
        'policy_version': POLICY_VERSION,
        'selection': {'make_id': config['make_id'], 'model_id': config['model_id'],
                      'model_year': config['model_year'], 'engine_id': config['engine_id']},
        'mode': 'confirmed', 'include_reference': False, 'browse_all': False,
        'eligible': [{'unit_id': unit, 'state': 'confirmed',
                      'reason_codes': ['explicit_source'], 'evidence_ids': [],
                      'review_event_ids': []}],
    }
    value['fingerprint'] = scope_fingerprint(value)
    return value


class TestApplicabilitySidecars(unittest.TestCase):
    def setUp(self):
        self.vocabulary = make_vocabulary()
        self.manifest = make_manifest()
        self.evidence = make_evidence(self.manifest, self.vocabulary)
        self.review = make_review(self.evidence, self.vocabulary)
        self.library = make_library(self.manifest, self.vocabulary, self.review)
        self.scope = make_scope(self.library, self.vocabulary,
                                self.evidence['units'][0]['id'])

    def test_positive_records_and_unchanged_v1(self):
        self.assertIs(validate_manifest(self.manifest), self.manifest)
        self.assertIs(validate_vocabulary(self.vocabulary), self.vocabulary)
        self.assertIs(validate_evidence(self.evidence, self.manifest, self.vocabulary),
                      self.evidence)
        self.assertIs(validate_review_overlay(self.review, self.evidence,
                                              self.vocabulary), self.review)
        index = {'packages/authored-source': self.library['packages'][0]}
        self.assertIs(validate_library(self.library, index), self.library)
        self.assertIs(validate_scope(self.scope, self.library, self.vocabulary,
                                     {self.evidence['units'][0]['id']},
                                     {self.evidence['assertions'][0]['id']},
                                     {self.review['events'][1]['id']}), self.scope)

    def test_json_schemas_accept_example_when_available(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('optional jsonschema is not installed')
        examples = (
            ('vehicle-vocabulary-v1', self.vocabulary),
            ('applicability-evidence-v1', self.evidence),
            ('applicability-review-v1', self.review),
            ('service-manual-library-v1', self.library),
            ('vehicle-scope-v1', self.scope),
        )
        for name, record in examples:
            with self.subTest(schema=name):
                with open(os.path.join(ROOT, 'schemas', name + '.schema.json'),
                          encoding='utf-8') as file:
                    schema = json.load(file)
                jsonschema.Draft202012Validator.check_schema(schema)
                jsonschema.validate(record, schema)

    def test_vocabulary_rejects_dangling_ids_and_cross_make_tuple(self):
        value = copy.deepcopy(self.vocabulary)
        value['models'][0]['make_id'] = value['makes'][1]['id']
        value['revision'] = digest({k: v for k, v in value.items() if k != 'revision'})
        with self.assertRaises(ContractError):
            validate_vocabulary(value)
        value = copy.deepcopy(self.vocabulary)
        value['configurations'][0]['make_id'] = value['makes'][1]['id']
        with self.assertRaises(ContractError):
            validate_vocabulary(value)

    def test_aliases_require_evidence_and_nonoverlapping_targets(self):
        value = copy.deepcopy(self.vocabulary)
        value['aliases'][0]['evidence']['citation']['path'] = '../outside'
        with self.assertRaises(ContractError):
            validate_vocabulary(value)

    def test_invalid_year_ranges_are_rejected(self):
        value = copy.deepcopy(self.vocabulary)
        value['aliases'][0]['year_start'] = 2004
        value['aliases'][0]['year_end'] = 2003
        with self.assertRaisesRegex(ContractError, 'invalid alias year range'):
            validate_vocabulary(value)
        value = copy.deepcopy(self.evidence)
        value['assertions'][0]['alternatives'][0]['year'] = {
            'state': 'range', 'start': 2005, 'end': 2002}
        with self.assertRaisesRegex(ContractError, 'invalid year range'):
            validate_evidence(value, self.manifest, self.vocabulary)
        value = copy.deepcopy(self.vocabulary)
        other = copy.deepcopy(value['aliases'][0])
        other['target_id'] = value['models'][1]['id']
        value['aliases'].append(other)
        with self.assertRaises(ContractError):
            validate_vocabulary(value)

    def test_evidence_rejects_invalid_tuple_cross_product_and_unbounded_all(self):
        value = copy.deepcopy(self.evidence)
        value['assertions'][0]['alternatives'][0]['engine'] = exact(
            self.vocabulary['engines'][1]['id'])
        with self.assertRaises(ContractError):
            validate_evidence(value, self.manifest, self.vocabulary)
        value = copy.deepcopy(self.evidence)
        value['assertions'][0]['alternatives'][0]['engine'] = [
            exact(self.vocabulary['engines'][0]['id']),
            exact(self.vocabulary['engines'][1]['id']),
        ]
        with self.assertRaises(ContractError):
            validate_evidence(value, self.manifest, self.vocabulary)
        value = copy.deepcopy(self.evidence)
        alt = value['assertions'][0]['alternatives'][0]
        alt['make'] = {'state': 'unknown'}
        alt['model'] = {'state': 'unknown'}
        alt['engine'] = {'state': 'all_in_scope'}
        with self.assertRaises(ContractError):
            validate_evidence(value, self.manifest, self.vocabulary)

    def test_unknown_and_explicit_all_are_distinct(self):
        value = copy.deepcopy(self.evidence)
        alt = value['assertions'][0]['alternatives'][0]
        alt['engine'] = {'state': 'all_in_scope'}
        assertion = value['assertions'][0]
        assertion['digest'] = assertion_digest(assertion)
        assertion['id'] = sidecar_id('ev', value['source_id'], assertion['subject_id'],
                                     assertion['digest'])
        value['revision'] = evidence_revision(value)
        validate_evidence(value, self.manifest, self.vocabulary)
        self.assertNotEqual(alt['engine'], {'state': 'unknown'})

    def test_mixed_text_cannot_be_searched_as_whole_document(self):
        value = copy.deepcopy(self.evidence)
        value['units'][0]['search'] = {'state': 'whole'}
        with self.assertRaisesRegex(ContractError, 'mixed-content'):
            validate_evidence(value, self.manifest, self.vocabulary)

    def test_ocr_and_filename_hints_cannot_claim_automatic_support(self):
        for field, new_value in (('provenance', 'ocr'), ('derivation', 'filename_hint')):
            value = copy.deepcopy(self.evidence)
            value['assertions'][0][field] = new_value
            with self.subTest(field=field), self.assertRaisesRegex(
                ContractError, 'automatic source support'
            ):
                validate_evidence(value, self.manifest, self.vocabulary)

    def test_review_rejects_unbound_approval_and_invalid_transition(self):
        value = copy.deepcopy(self.review)
        value['events'][1]['evidence_bindings'] = []
        with self.assertRaises(ContractError):
            validate_review_overlay(value, self.evidence, self.vocabulary)

    def test_review_revoke_is_scoped_and_terminal(self):
        value = copy.deepcopy(self.review)
        accepted = value['events'][1]
        revoked = {k: copy.deepcopy(v) for k, v in accepted.items() if k != 'id'}
        revoked['action'] = 'revoke'
        revoked['prior_event_id'] = accepted['id']
        revoked['timestamp'] = '2026-09-25T12:01:00Z'
        revoked['reason'] = 'Reviewer withdrew the mapping.'
        revoked['id'] = sidecar_id('review', digest(revoked))
        value['events'].append(revoked)
        value['revision'] = digest({k: v for k, v in value.items() if k != 'revision'})
        validate_review_overlay(value, self.evidence, self.vocabulary)
        value['events'].append(copy.deepcopy(revoked))
        with self.assertRaises(ContractError):
            validate_review_overlay(value, self.evidence, self.vocabulary)
        value = copy.deepcopy(self.review)
        value['events'][1]['prior_event_id'] = sidecar_id('review', 'missing')
        with self.assertRaises(ContractError):
            validate_review_overlay(value, self.evidence, self.vocabulary)
        value = copy.deepcopy(self.review)
        value['events'][1]['target_configuration_ids'] = [
            self.vocabulary['configurations'][1]['id']]
        with self.assertRaises(ContractError):
            validate_review_overlay(value, self.evidence, self.vocabulary)

    def test_review_is_bound_to_exact_evidence_and_policy_snapshot(self):
        changed = copy.deepcopy(self.evidence)
        changed['revision'] = TWO
        with self.assertRaisesRegex(ContractError, 'canonical record content'):
            validate_review_overlay(self.review, changed, self.vocabulary)
        value = copy.deepcopy(self.review)
        value['policy_version'] = 'later-policy'
        with self.assertRaisesRegex(ContractError, 'policy'):
            validate_review_overlay(value, self.evidence, self.vocabulary)

    def test_historical_approval_survives_but_becomes_stale(self):
        changed = copy.deepcopy(self.evidence)
        changed['assertions'] = []
        changed['revision'] = evidence_revision(changed)
        review = copy.deepcopy(self.review)
        review['evidence_snapshots'][0]['revision'] = changed['revision']
        review['revision'] = digest({k: v for k, v in review.items() if k != 'revision'})
        validate_review_overlay(review, changed, self.vocabulary,
                                {self.evidence['revision']: self.evidence})
        self.assertTrue(review_event_is_stale(review['events'][1], review))

    def test_library_rejects_dangling_packages_and_successors(self):
        index = {}
        with self.assertRaisesRegex(ContractError, 'absent or has changed'):
            validate_library(self.library, index)
        value = copy.deepcopy(self.library)
        value['packages'][0]['status'] = 'superseded'
        value['packages'][0]['superseded_by'] = sidecar_id('occ', 'missing')
        with self.assertRaises(ContractError):
            validate_library(value)

    def test_scope_rejects_stale_fingerprint_widening_and_dangling_units(self):
        value = copy.deepcopy(self.scope)
        value['selection']['make_id'] = self.vocabulary['makes'][1]['id']
        with self.assertRaises(ContractError):
            validate_scope(value, self.library, self.vocabulary)
        value = copy.deepcopy(self.scope)
        value['eligible'][0]['state'] = 'possible'
        with self.assertRaisesRegex(ContractError, 'confirmed mode'):
            validate_scope(value, self.library, self.vocabulary)
        value = copy.deepcopy(self.scope)
        value['eligible'][0]['unit_id'] = sidecar_id('unit', 'missing')
        with self.assertRaisesRegex(ContractError, 'dangling eligible unit'):
            validate_scope(value, self.library, self.vocabulary,
                           {self.evidence['units'][0]['id']})
        value = copy.deepcopy(self.scope)
        value['selection'] = {}
        value['fingerprint'] = scope_fingerprint(value)
        with self.assertRaisesRegex(ContractError, 'empty non-browse'):
            validate_scope(value, self.library, self.vocabulary)
        value = copy.deepcopy(self.scope)
        value['eligible'][0]['evidence_ids'] = [self.evidence['assertions'][0]['id']]
        with self.assertRaisesRegex(ContractError, 'dangling evidence ID'):
            validate_scope(value, self.library, self.vocabulary,
                           evidence_ids=set())

    def test_language_independent_truth_table_has_expected_reason_codes(self):
        path = os.path.join(ROOT, 'tests', 'fixtures', 'applicability_decisions_v1.json')
        with open(path, encoding='utf-8') as file:
            table = json.load(file)
        self.assertEqual(table['contract'], 'vehicle-applicability-decisions/v1')
        ids = [case['id'] for case in table['cases']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 18)
        for case in table['cases']:
            self.assertIn(case['expected']['state'],
                          ('confirmed', 'possible', 'reference', 'excluded', 'unmapped'))
            self.assertIn(case['expected']['reason_code'], REASON_CODES)
            if case['expected']['state'] in ('excluded', 'unmapped'):
                self.assertFalse(case['expected']['search_eligible'])


if __name__ == '__main__':
    unittest.main()
