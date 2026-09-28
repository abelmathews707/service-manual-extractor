"""B1 scope regressions using authored evidence, never distributed manual text."""

import copy
import unittest

from test_applicability_contracts import exact, make_vocabulary
from test_matching_review import _alt, _assertion, _base, _set_assertions

from acceptance.b1_pilot_vocabulary import extend_vocabulary
from sme.applicability_contracts import configuration_id, digest, unit_id
from sme.matching import match_unit
from sme.review import decide, new_overlay, propose
from sme.vehicle_interpretation import interpret_statement


class PilotVocabularyTests(unittest.TestCase):
    def test_old_configurations_preserved_and_same_displacement_fuels_distinct(self):
        accepted = make_vocabulary()
        vocabulary = extend_vocabulary(accepted)
        self.assertEqual(vocabulary['configurations'][:len(accepted['configurations'])],
                         accepted['configurations'])
        engines = [item for item in vocabulary['engines'] if item['displacement_l'] == 6.8]
        self.assertEqual({item['fuel'] for item in engines}, {'gasoline', 'cng'})
        self.assertEqual(len({item['id'] for item in engines}), 2)
        alternatives, resolved = interpret_statement('2003 F-250 6.8L', vocabulary)
        self.assertFalse(resolved)
        self.assertEqual(alternatives[0]['engine']['state'], 'unknown')
        alternatives, _ = interpret_statement('6.8L E/F-Series (A/T)', vocabulary)
        gas = next(item for item in engines if item['fuel'] == 'gasoline')
        self.assertEqual(alternatives[0]['engine'], exact(gas['id']))


class ReviewedAncestryTests(unittest.TestCase):
    def fixture(self, *, heading_provenance='native', heading_selector='heading'):
        vocabulary, manifest, evidence, selection = _base()
        config = vocabulary['configurations'][0]
        qualifiers = {'transmission': '4R100', 'drivetrain': '4WD'}
        config['qualifiers'] = qualifiers
        config['id'] = configuration_id(config['make_id'], config['model_id'],
                                         config['model_year'], config['engine_id'], qualifiers)
        vocabulary['revision'] = digest({k: v for k, v in vocabulary.items() if k != 'revision'})
        evidence['vocabulary_revision'] = vocabulary['revision']
        source_unit = evidence['units'][0]
        source_unit['kind'] = 'section'
        source_unit['id'] = unit_id(evidence['generation_sha256'], source_unit['document_id'],
                                    source_unit['kind'], source_unit['selector'])
        unit = evidence['units'][0]['id']
        catalog = _assertion(evidence, manifest['publications'][0]['id'],
                             [_alt(config, engine={'state': 'unknown'})], support='proposal',
                             derivation='explicit_structured', descendants=True)
        heading = _assertion(evidence, unit, [_alt(config)], support='proposal',
                             derivation='title_hint', provenance=heading_provenance)
        heading['alternatives'][0] = {field: {'state': 'unknown'}
                                    for field in ('make', 'model', 'year')} | {
            'engine': exact(config['engine_id']), 'qualifiers': {}}
        heading['selector'] = heading_selector
        from sme.applicability_contracts import assertion_digest, sidecar_id
        heading['digest'] = assertion_digest(heading)
        heading['id'] = sidecar_id('ev', evidence['source_id'], unit, heading['digest'])
        _set_assertions(evidence, catalog, heading)
        review = propose(new_overlay(evidence, vocabulary), evidence, vocabulary,
                         source_id=evidence['source_id'], subject_id=unit,
                         relation='section_applies', target_configuration_ids=[config['id']],
                         evidence_ids=[catalog['id'], heading['id']], reviewer='authored',
                         timestamp='2026-09-28T12:00:00Z', reason='Exact original reviewed')
        review = decide(review, evidence, vocabulary,
                        prior_event_id=review['events'][-1]['id'], action='accept',
                        reviewer='authored', timestamp='2026-09-28T12:01:00Z',
                        reason='Original heading/catalog independently checked')
        return vocabulary, manifest, evidence, selection | {'qualifiers': qualifiers}, review, unit

    def match(self, fixture, selection=None, **kwargs):
        vocabulary, manifest, evidence, selected, review, unit = fixture
        return match_unit(evidence, manifest, vocabulary, unit,
                          selected if selection is None else selection, review=review, **kwargs)

    def test_reviewed_heading_and_catalog_allow_exact_vehicle_only(self):
        fixture = self.fixture()
        self.assertEqual(self.match(fixture)['state'], 'confirmed')
        other = fixture[0]['configurations'][1]
        selected = {k: other[k] for k in ('make_id', 'model_id', 'model_year', 'engine_id')}
        self.assertFalse(self.match(fixture, selected, mode='include_possible')['search_eligible'])
        unreviewed = list(fixture)
        unreviewed[4] = None
        self.assertFalse(self.match(unreviewed)['search_eligible'])

    def test_qualifier_changes_cannot_reuse_configuration_approval(self):
        fixture = self.fixture()
        selected = fixture[3]
        self.assertNotEqual(self.match(fixture, {k: v for k, v in selected.items()
                                                if k != 'qualifiers'})['state'], 'confirmed')
        for qualifiers in ({'transmission': 'manual', 'drivetrain': '4WD'},
                           {'transmission': '4R100', 'drivetrain': '2WD'}):
            with self.subTest(qualifiers=qualifiers):
                self.assertFalse(self.match(fixture, selected | {'qualifiers': qualifiers},
                                             mode='include_possible')['search_eligible'])

    def test_filename_and_ocr_hints_cannot_fill_reviewed_identity(self):
        for provenance, selector in (('catalog', 'document-title'), ('ocr', 'heading'),
                                     ('native', 'document-title')):
            with self.subTest(provenance=provenance, selector=selector):
                self.assertNotEqual(self.match(self.fixture(heading_provenance=provenance,
                                                             heading_selector=selector))['state'],
                                    'confirmed')

    def test_review_must_bind_the_actual_heading_and_catalog(self):
        fixture = self.fixture()
        vocabulary, manifest, evidence, selection, _, unit = fixture
        for assertion in evidence['assertions']:
            review = propose(new_overlay(evidence, vocabulary), evidence, vocabulary,
                             source_id=evidence['source_id'], subject_id=unit,
                             relation='section_applies',
                             target_configuration_ids=[vocabulary['configurations'][0]['id']],
                             evidence_ids=[assertion['id']], reviewer='authored',
                             timestamp='2026-09-28T12:00:00Z', reason='Incomplete binding')
            review = decide(review, evidence, vocabulary,
                            prior_event_id=review['events'][-1]['id'], action='accept',
                            reviewer='authored', timestamp='2026-09-28T12:01:00Z',
                            reason='Only one dimension reviewed')
            self.assertNotEqual(match_unit(evidence, manifest, vocabulary, unit, selection,
                                            review=review)['state'], 'confirmed')

    def test_source_child_exclusion_still_defeats_exact_unit_review(self):
        fixture = list(self.fixture())
        evidence = copy.deepcopy(fixture[2])
        exclusion = _assertion(evidence, fixture[-1], [_alt(fixture[0]['configurations'][0])],
                               intent='exclude')
        evidence['assertions'].append(exclusion)
        from sme.applicability_contracts import evidence_revision
        evidence['revision'] = evidence_revision(evidence)
        # Exercise the decision engine without retargeting a now-stale old review.
        result = match_unit(evidence, fixture[1], fixture[0], fixture[-1], fixture[3],
                            validate=False, review=fixture[4])
        self.assertEqual(result['reason_codes'], ['conflicting_child'])
        self.assertFalse(result['search_eligible'])


if __name__ == '__main__':
    unittest.main()
