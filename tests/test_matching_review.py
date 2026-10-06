"""A5 decisions and review lifecycle against the frozen A2 truth table."""

import copy
import json
import os
import tempfile
import unittest

from test_applicability_contracts import exact, make_evidence, make_manifest, make_vocabulary
from test_ford_adapter import _files
from test_formats import make_arc

from sme.applicability_contracts import (
    POLICY_VERSION,
    assertion_digest,
    configuration_id,
    digest,
    evidence_revision,
    sidecar_id,
    validate_review_overlay,
)
from sme.contract import ContractError, load_manifest
from sme.evidence import capture_evidence
from sme.ford_adapter import import_ford
from sme.matching import match_unit
from sme.review import (
    decide,
    load_overlay,
    new_overlay,
    propose,
    rebase,
    save_overlay,
    shared_content_proposals,
)

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures',
                       'applicability_decisions_v1.json')


def _base():
    vocabulary, manifest = make_vocabulary(), make_manifest()
    evidence = make_evidence(manifest, vocabulary)
    unit = evidence['units'][0]
    unit['mixed_content'] = False
    unit['search'] = {'state': 'whole'}
    evidence['revision'] = evidence_revision(evidence)
    config = vocabulary['configurations'][0]
    selection = {'make_id': config['make_id'], 'model_id': config['model_id'],
                 'model_year': config['model_year'], 'engine_id': config['engine_id']}
    return vocabulary, manifest, evidence, selection


def _alt(config, *, engine=None, qualifiers=None, make=None):
    return {'make': make or exact(config['make_id']),
            'model': exact(config['model_id']),
            'year': exact(config['model_year']),
            'engine': engine or exact(config['engine_id']),
            'qualifiers': qualifiers or {}}


def _assertion(evidence, subject, alternatives, *, support='source_supported',
               intent='include', provenance='native', derivation='explicit_text',
               descendants=False, statement='Authored vehicle evidence'):
    record = {'subject_id': subject, 'statement': statement,
              'citation': {'kind': 'path', 'path': 'pages/engine.html'},
              'intent': intent, 'applies_to_descendants': descendants,
              'derivation': derivation, 'provenance': provenance,
              'support': support, 'alternatives': alternatives}
    record['digest'] = assertion_digest(record)
    record['id'] = sidecar_id('ev', evidence['source_id'], subject, record['digest'])
    return record


def _set_assertions(evidence, *assertions):
    evidence['assertions'] = list(assertions)
    evidence['revision'] = evidence_revision(evidence)


def _review_for(evidence, vocabulary, unit_id, target_id, relation='section_applies'):
    overlay = new_overlay(evidence, vocabulary)
    overlay = propose(overlay, evidence, vocabulary,
                      source_id=evidence['source_id'], subject_id=unit_id,
                      relation=relation, target_configuration_ids=[target_id],
                      evidence_ids=[evidence['assertions'][0]['id']], reviewer='test',
                      timestamp='2026-09-26T10:00:00Z', reason='Cited review lead')
    return overlay


class FrozenDecisionTests(unittest.TestCase):
    def test_all_frozen_cases(self):
        with open(FIXTURE, encoding='utf-8') as stream:
            cases = json.load(stream)['cases']
        self.assertEqual(len(cases), 25)
        for case in cases:
            with self.subTest(case=case['id']):
                result = self._case(case['id'])
                self.assertEqual({key: result[key] for key in
                                  ('state', 'search_eligible')},
                                 {key: case['expected'][key] for key in
                                  ('state', 'search_eligible')})
                self.assertEqual(result['reason_codes'][0],
                                 case['expected']['reason_code'])

    def _case(self, name):
        vocab, manifest, evidence, selection = _base()
        unit_id = evidence['units'][0]['id']
        config = vocab['configurations'][0]
        gm = vocab['configurations'][1]
        mode = 'confirmed'
        review = None
        include_reference = False
        if name in ('same-displacement-different-engine', 'unrelated-car-fixture'):
            other = gm if name != 'unrelated-car-fixture' else vocab['configurations'][2]
            _set_assertions(evidence, _assertion(evidence, unit_id, [_alt(other)]))
        elif name == 'ford-publisher-lincoln-vehicle':
            lincoln = sidecar_id('make', 'lincoln')
            navigator = sidecar_id('model', lincoln, 'navigator')
            engine = sidecar_id('engine', 'ford', '5-4-gasoline')
            vocab['makes'].append({'id': lincoln, 'key': 'lincoln', 'name': 'Lincoln'})
            vocab['models'].append({'id': navigator, 'key': 'navigator',
                                    'name': 'Navigator', 'make_id': lincoln})
            vocab['engines'].append({'id': engine, 'key': '5-4-gasoline',
                                     'name': '5.4L gasoline', 'manufacturer': 'ford',
                                     'fuel': 'gasoline', 'displacement_l': 5.4})
            lincoln_config = {'id': configuration_id(lincoln, navigator, 2003, engine),
                              'make_id': lincoln, 'model_id': navigator,
                              'model_year': 2003, 'engine_id': engine,
                              'qualifiers': {}}
            vocab['configurations'].append(lincoln_config)
            vocab['revision'] = digest({key: value for key, value in vocab.items()
                                        if key != 'revision'})
            evidence['vocabulary_revision'] = vocab['revision']
            _set_assertions(evidence, _assertion(evidence, unit_id,
                            [_alt(lincoln_config)]))
        elif name == 'correlated-alternatives':
            ford = config['make_id']
            f250 = config['model_id']
            diesel73 = sidecar_id('engine', 'ford', '7-3-diesel')
            vocab['engines'].append({'id': diesel73, 'key': '7-3-diesel',
                                     'name': '7.3L diesel', 'manufacturer': 'ford',
                                     'fuel': 'diesel', 'displacement_l': 7.3})
            for engine in (config['engine_id'], diesel73):
                vocab['configurations'].append({
                    'id': configuration_id(ford, f250, 2002, engine),
                    'make_id': ford, 'model_id': f250, 'model_year': 2002,
                    'engine_id': engine, 'qualifiers': {}})
            vocab['revision'] = digest({key: value for key, value in vocab.items()
                                        if key != 'revision'})
            evidence['vocabulary_revision'] = vocab['revision']
            _set_assertions(evidence, _assertion(evidence, unit_id,
                            [_alt(config), _alt(vocab['configurations'][-1])]))
            selection = {'make_id': ford, 'model_id': f250,
                         'model_year': 2002, 'engine_id': config['engine_id']}
        elif name in ('unknown-engine', 'unknown-engine-confirmed-mode'):
            mode = 'include_possible' if name == 'unknown-engine' else 'confirmed'
            _set_assertions(evidence, _assertion(evidence, unit_id,
                            [_alt(config, engine={'state': 'unknown'})],
                            support='proposal', derivation='title_hint',
                            provenance='catalog'))
        elif name == 'explicit-all-engines-bounded':
            _set_assertions(evidence, _assertion(evidence, unit_id,
                            [_alt(config, engine={'state': 'all_in_scope'})]))
        elif name == 'make-only-partial-filter':
            selection = {'make_id': config['make_id']}
            mode = 'include_possible'
        elif name == 'missing-required-transmission':
            mode = 'include_possible'
            _set_assertions(evidence, _assertion(evidence, unit_id,
                            [_alt(config, qualifiers={'transmission': exact('automatic')})]))
        elif name == 'child-excludes-parent-match':
            parent = manifest['publications'][0]['id']
            _set_assertions(evidence,
                            _assertion(evidence, parent, [_alt(config)], descendants=True),
                            _assertion(evidence, unit_id, [_alt(config)], intent='exclude'))
        elif name in ('first-page-pdf-hint', 'ocr-engine-qualifier-unreviewed'):
            mode = 'include_possible'
            provenance = 'ocr' if name.startswith('ocr') else 'catalog'
            _set_assertions(evidence, _assertion(evidence, unit_id, [_alt(config)],
                            support='proposal', provenance=provenance,
                            derivation='title_hint' if provenance == 'catalog'
                            else 'explicit_text'))
        elif name == 'mixed-engine-pdf-page':
            evidence['units'][0]['mixed_content'] = True
            evidence['units'][0]['search'] = {'state': 'metadata_only'}
            evidence['revision'] = evidence_revision(evidence)
        elif name in ('generic-dtc-opt-in', 'generic-dtc-default'):
            manifest['publications'][0]['kind'] = 'reference'
            # Manifest hash changed, so rebuild the evidence snapshot.
            evidence['manifest_sha256'] = digest(manifest)
            evidence['generation_sha256'] = digest([evidence['manifest_sha256'],
                                                     evidence['content_sha256']])
            old_unit = evidence['units'][0]['id']
            from sme.applicability_contracts import unit_id as make_unit_id
            evidence['units'][0]['id'] = make_unit_id(
                evidence['generation_sha256'], evidence['units'][0]['document_id'],
                evidence['units'][0]['kind'], evidence['units'][0]['selector'])
            unit_id = evidence['units'][0]['id']
            self.assertNotEqual(old_unit, unit_id)
            _set_assertions(evidence, _assertion(evidence, unit_id, [_alt(config)]))
            include_reference = name == 'generic-dtc-opt-in'
        elif name in ('unknown-make-ford-filter', 'legacy-blank-make'):
            _set_assertions(evidence, _assertion(evidence, unit_id,
                            [{'make': {'state': 'unknown'},
                              'model': {'state': 'unknown'},
                              'year': {'state': 'unknown'},
                              'engine': {'state': 'unknown'}, 'qualifiers': {}}],
                            support='proposal', derivation='heuristic'))
        elif name == 'reviewed-shared-section':
            _set_assertions(evidence, _assertion(evidence, unit_id, [_alt(gm)]))
            review = _review_for(evidence, vocab, unit_id, config['id'])
            review = decide(review, evidence, vocab,
                            prior_event_id=review['events'][0]['id'], action='accept',
                            reviewer='test', timestamp='2026-09-26T11:00:00Z',
                            reason='Original procedure checked')
        elif name in ('shared-part-only', 'pending-cross-make'):
            _set_assertions(evidence, _assertion(evidence, unit_id, [_alt(gm)]))
            relation = 'part_mentioned' if name == 'shared-part-only' else 'section_applies'
            review = _review_for(evidence, vocab, unit_id, config['id'], relation)
        elif name == 'rejected-or-revoked-approval':
            _set_assertions(evidence, _assertion(evidence, unit_id, [_alt(gm)]))
            review = _review_for(evidence, vocab, unit_id, config['id'])
            review = decide(review, evidence, vocab,
                            prior_event_id=review['events'][0]['id'], action='accept',
                            reviewer='test', timestamp='2026-09-26T11:00:00Z',
                            reason='Original checked')
            review = decide(review, evidence, vocab,
                            prior_event_id=review['events'][1]['id'], action='revoke',
                            reviewer='test', timestamp='2026-09-26T12:00:00Z',
                            reason='Decision withdrawn')
        elif name == 'stale-evidence-review':
            _set_assertions(evidence, _assertion(evidence, unit_id, [_alt(gm)]))
            old = copy.deepcopy(evidence)
            review = _review_for(evidence, vocab, unit_id, config['id'])
            review = decide(review, evidence, vocab,
                            prior_event_id=review['events'][0]['id'], action='accept',
                            reviewer='test', timestamp='2026-09-26T11:00:00Z',
                            reason='Original checked')
            evidence['assertions'][0]['statement'] += ' corrected edition'
            evidence['assertions'][0]['digest'] = assertion_digest(evidence['assertions'][0])
            evidence['assertions'][0]['id'] = sidecar_id(
                'ev', evidence['source_id'], unit_id,
                evidence['assertions'][0]['digest'])
            evidence['revision'] = evidence_revision(evidence)
            review = rebase(review, evidence, vocab, {old['revision']: old})
            return match_unit(evidence, manifest, vocab, unit_id, selection,
                              review=review, evidence_history={old['revision']: old})
        elif name == 'package-without-sidecar':
            return match_unit(None, manifest, vocab, unit_id, selection)
        elif name == 'empty-scope':
            selection = {}
        return match_unit(evidence, manifest, vocab, unit_id, selection,
                          mode=mode, include_reference=include_reference, review=review)


class ReviewLifecycleTests(unittest.TestCase):
    def test_ford_import_evidence_inherits_to_matching_page(self):
        vocab = make_vocabulary()
        with tempfile.TemporaryDirectory() as root:
            directory = os.path.join(root, 'disc', 'content', 'useni4')
            os.makedirs(directory)
            with open(os.path.join(directory, 'SAA.arc'), 'wb') as stream:
                stream.write(make_arc(dict(_files())))
            package = os.path.join(root, 'package')
            import_ford(os.path.join(root, 'disc'), package,
                        ['content/useni4/saa.arc'])
            evidence = capture_evidence(package, vocab)
            manifest = load_manifest(os.path.join(package, '.sme-manifest.json'))
            unit = next(item for item in evidence['units']
                        if item['search']['state'] == 'whole')
            ford = vocab['configurations'][0]
            gm = vocab['configurations'][1]

            def selected(config):
                return {'make_id': config['make_id'], 'model_id': config['model_id'],
                        'model_year': config['model_year'],
                        'engine_id': config['engine_id']}

            self.assertEqual(match_unit(evidence, manifest, vocab, unit['id'],
                                        selected(ford))['state'], 'confirmed')
            self.assertEqual(match_unit(evidence, manifest, vocab, unit['id'],
                                        selected(gm))['state'], 'excluded')

    def test_metadata_only_unit_never_enters_text_search(self):
        vocab, manifest, evidence, selection = _base()
        evidence['units'][0]['search'] = {'state': 'metadata_only'}
        evidence['revision'] = evidence_revision(evidence)
        result = match_unit(evidence, manifest, vocab,
                            evidence['units'][0]['id'], selection)
        self.assertEqual(result['state'], 'confirmed')
        self.assertFalse(result['search_eligible'])

    def test_child_source_conflict_defeats_parent_review(self):
        vocab, manifest, evidence, selection = _base()
        parent = manifest['publications'][0]['id']
        unit = evidence['units'][0]['id']
        gm = vocab['configurations'][1]
        _set_assertions(evidence,
                        _assertion(evidence, parent, [_alt(gm)], descendants=True),
                        _assertion(evidence, unit, [_alt(gm)]))
        review = _review_for(evidence, vocab, parent,
                             vocab['configurations'][0]['id'])
        review = decide(review, evidence, vocab,
                        prior_event_id=review['events'][0]['id'], action='accept',
                        reviewer='test', timestamp='2026-09-26T11:00:00Z',
                        reason='Parent accepted')
        result = match_unit(evidence, manifest, vocab, unit, selection, review=review)
        self.assertEqual((result['state'], result['reason_codes']),
                         ('excluded', ['conflicting_child']))

    def test_portable_append_only_overlay_and_transitions(self):
        vocab, manifest, evidence, selection = _base()
        unit = evidence['units'][0]['id']
        target = vocab['configurations'][0]['id']
        overlay = _review_for(evidence, vocab, unit, target)
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, 'reviews.json')
            save_overlay(path, overlay, evidence, vocab)
            self.assertEqual(load_overlay(path, evidence, vocab), overlay)
            accepted = decide(overlay, evidence, vocab,
                              prior_event_id=overlay['events'][0]['id'], action='accept',
                              reviewer='test', timestamp='2026-09-26T11:00:00Z',
                              reason='Cited decision')
            save_overlay(path, accepted, evidence, vocab)
            self.assertEqual(match_unit(evidence, manifest, vocab, unit, selection,
                                        review=accepted)['state'], 'confirmed')
            with self.assertRaises(ContractError):
                save_overlay(path, overlay, evidence, vocab)
            revoked = decide(accepted, evidence, vocab,
                             prior_event_id=accepted['events'][1]['id'], action='revoke',
                             reviewer='test', timestamp='2026-09-26T12:00:00Z',
                             reason='Evidence overturned')
            save_overlay(path, revoked, evidence, vocab)
            self.assertEqual(len(load_overlay(path, evidence, vocab)['events']), 3)
            with self.assertRaises(ContractError):
                decide(revoked, evidence, vocab,
                       prior_event_id=accepted['events'][1]['id'], action='revoke',
                       reviewer='test', timestamp='2026-09-26T13:00:00Z',
                       reason='Second terminal action')

    def test_same_evidence_reimport_preserves_review(self):
        vocab, _, evidence, _ = _base()
        unit = evidence['units'][0]['id']
        overlay = _review_for(evidence, vocab, unit, vocab['configurations'][0]['id'])
        accepted = decide(overlay, evidence, vocab,
                          prior_event_id=overlay['events'][0]['id'], action='accept',
                          reviewer='test', timestamp='2026-09-26T11:00:00Z',
                          reason='Verified')
        self.assertEqual(validate_review_overlay(accepted, copy.deepcopy(evidence),
                                                 vocab), accepted)
        self.assertEqual(accepted['policy_version'], POLICY_VERSION)

    def test_rejection_and_supersession_keep_history(self):
        vocab, _, evidence, _ = _base()
        unit = evidence['units'][0]['id']
        target = vocab['configurations'][0]['id']
        proposal = _review_for(evidence, vocab, unit, target)
        rejected = decide(proposal, evidence, vocab,
                          prior_event_id=proposal['events'][0]['id'], action='reject',
                          reviewer='test', timestamp='2026-09-26T11:00:00Z',
                          reason='Not the same procedure')
        self.assertEqual(len(rejected['events']), 2)
        accepted = decide(proposal, evidence, vocab,
                          prior_event_id=proposal['events'][0]['id'], action='accept',
                          reviewer='test', timestamp='2026-09-26T11:00:00Z',
                          reason='Cited original page')
        superseded = decide(accepted, evidence, vocab,
                            prior_event_id=accepted['events'][1]['id'],
                            action='supersede', reviewer='test',
                            timestamp='2026-09-26T12:00:00Z',
                            reason='New edition requires new proposal')
        self.assertEqual([event['action'] for event in superseded['events']],
                         ['propose', 'accept', 'supersede'])

    def test_shared_content_only_generates_bounded_review_leads(self):
        vocab, _, evidence, _ = _base()
        other = copy.deepcopy(evidence)
        other['source_id'] = sidecar_id('make', 'other').replace('make_', 'src_')
        records = []
        for item in (evidence, other):
            records.append({'evidence': item, 'content': {'documents': [{
                'id': item['units'][0]['document_id'],
                'text': ('This common section mentions ABCD-1234 and describes '
                         'the same authored diagnostic flow in enough detail to '
                         'qualify as a duplicate.')} ]}})
        leads = shared_content_proposals(records, vocab, limit=1)
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]['relation'], 'duplicate_content')
        self.assertTrue(leads[0]['basis']['same_text'])
        self.assertEqual(leads[0]['target_configuration_ids'],
                         [vocab['configurations'][0]['id']])
        self.assertNotEqual(leads[0]['relation'], 'section_applies')
        records[0]['content']['documents'][0]['text'] = 'For details see Engine table.'
        records[1]['content']['documents'][0]['text'] = 'Different procedure text.'
        records[1]['content']['documents'][0]['title'] = 'Engine table'
        link_leads = shared_content_proposals(records, vocab, limit=1)
        self.assertEqual(len(link_leads), 1)
        self.assertEqual(link_leads[0]['relation'], 'section_applies')
        self.assertTrue(link_leads[0]['basis']['explicit_cross_reference'])


if __name__ == '__main__':
    unittest.main()
