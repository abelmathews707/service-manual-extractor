"""A6 multi-source pre-search and atomic export gates."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_applicability_contracts import make_vocabulary
from test_ford_adapter import _files
from test_formats import make_arc
from test_sources import pdf_bytes

from sme.applicability_contracts import (
    assertion_digest,
    configuration_id,
    digest,
    evidence_revision,
    sidecar_id,
)
from sme.contract import ContractError
from sme.evidence import capture_evidence
from sme.ford_adapter import import_ford
from sme.library import resolve_scope, verified_package
from sme.library_export import (
    ScopeCache,
    SearchCancelled,
    open_current,
    publish_library,
    search_export,
)
from sme.normalize import normalize_source
from sme.review import decide, new_overlay, propose
from sme.source import extract_source

HTML_FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'html_manual')


def selection(config):
    return {'make_id': config['make_id'], 'model_id': config['model_id'],
            'model_year': config['model_year'], 'engine_id': config['engine_id']}


class LibraryExportTests(unittest.TestCase):
    def _sources(self, root, vocabulary):
        disc = os.path.join(root, 'disc')
        archives = os.path.join(disc, 'content', 'useni4')
        os.makedirs(archives)
        for code in ('SAA', 'SBB'):
            Path(archives, code + '.arc').write_bytes(make_arc(dict(_files(code))))
        ford = os.path.join(root, 'ford-package')
        import_ford(disc, ford, ['content/useni4/saa.arc',
                                 'content/useni4/sbb.arc'])
        html = os.path.join(root, 'html-source')
        shutil.copytree(HTML_FIXTURE, html)
        extracted_html = os.path.join(root, 'html-extracted')
        html_package = os.path.join(root, 'html-package')
        extract_source(html, extracted_html)
        normalize_source(extracted_html, html_package)
        pdf = os.path.join(root, '2006-gm-article.pdf')
        Path(pdf).write_bytes(pdf_bytes(('2006 Chevrolet Silverado 1500 '
                                         '6.0L gasoline GM-only article',)))
        extracted_pdf = os.path.join(root, 'pdf-extracted')
        pdf_package = os.path.join(root, 'pdf-package')
        extract_source(pdf, extracted_pdf)
        normalize_source(extracted_pdf, pdf_package)
        packages = [ford, html_package, pdf_package]
        evidence = [capture_evidence(package, vocabulary) for package in packages]
        return packages, evidence

    def test_combined_ford_gm_html_never_loads_gm_shard_for_ford(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = make_vocabulary()
            packages, evidence = self._sources(root, vocabulary)
            review = new_overlay(evidence, vocabulary)
            sources = [{'package': package, 'evidence': item}
                       for package, item in zip(packages, evidence)]
            sources.append({'package': packages[0], 'evidence': evidence[0]})
            output = os.path.join(root, 'library')
            published = publish_library(output, sources, vocabulary, review,
                                        max_shard_chars=1000,
                                        discovery_report={'sources': [{
                                            'name': 'notes.txt', 'status': 'unsupported',
                                            'reason': 'not a supported manual'}]})
            self.assertEqual(published['packages'], 4)
            generation, index = open_current(
                output, current_review_revision=review['revision'])
            with open(os.path.join(generation, 'library.json'), encoding='utf-8') as stream:
                library = json.load(stream)
            self.assertEqual(len(library['packages']), 4)
            self.assertEqual(len({item['occurrence_id'] for item in library['packages']}), 4)
            self.assertEqual(index['unsupported_inputs'][0]['name'], 'notes.txt')
            read_texts = []

            def load(path):
                with open(path, encoding='utf-8') as stream:
                    items = json.load(stream)
                read_texts.extend(item['text'] for item in items)
                return items

            found = search_export(generation, index,
                                  selection(vocabulary['configurations'][0]),
                                  'pump', load_shard=load,
                                  current_review_revision=review['revision'])
            self.assertTrue(found['results'])
            self.assertTrue(found['loaded_shard_ids'])
            self.assertFalse(any('GM-only' in text for text in read_texts))
            self.assertTrue(all(len(item['occurrence_ids']) == 2
                                for item in found['results']))
            gm_only = search_export(generation, index,
                                    selection(vocabulary['configurations'][0]),
                                    'GM-only', load_shard=load,
                                    current_review_revision=review['revision'])
            self.assertEqual(gm_only['results'], [])
            self.assertFalse(any('GM-only' in text for text in read_texts))
            no_selection = search_export(generation, index, {}, 'pump',
                                         load_shard=load,
                                         current_review_revision=review['revision'])
            self.assertEqual(no_selection['results'], [])
            self.assertEqual(no_selection['loaded_shard_ids'], [])
            self.assertFalse(any('GM-only' in text for text in read_texts))
            with self.assertRaises(SearchCancelled):
                search_export(generation, index,
                              selection(vocabulary['configurations'][0]),
                              'pump', cancelled=lambda: True,
                              current_review_revision=review['revision'])

    def test_changed_review_and_failed_build_cannot_reactivate_old_scope(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = make_vocabulary()
            packages, evidence = self._sources(root, vocabulary)
            review = new_overlay(evidence, vocabulary)
            sources = [{'package': package, 'evidence': item}
                       for package, item in zip(packages, evidence)]
            output = os.path.join(root, 'library')
            first = publish_library(output, sources, vocabulary, review)
            unit = evidence[0]['units'][0]
            review = propose(review, evidence, vocabulary,
                             source_id=evidence[0]['source_id'],
                             subject_id=unit['id'], relation='section_applies',
                             target_configuration_ids=[vocabulary['configurations'][0]['id']],
                             evidence_ids=[evidence[0]['assertions'][1]['id']],
                             reviewer='test', timestamp='2026-09-26T10:00:00Z',
                             reason='Review original')
            review = decide(review, evidence, vocabulary,
                            prior_event_id=review['events'][0]['id'], action='accept',
                            reviewer='test', timestamp='2026-09-26T11:00:00Z',
                            reason='Accepted exact section')
            review = decide(review, evidence, vocabulary,
                            prior_event_id=review['events'][1]['id'], action='revoke',
                            reviewer='test', timestamp='2026-09-26T12:00:00Z',
                            reason='Withdrawn')

            def fail(_stage):
                raise RuntimeError('injected index publication failure')

            with self.assertRaisesRegex(RuntimeError, 'injected'):
                publish_library(output, sources, vocabulary, review,
                                before_activate=fail)
            with self.assertRaisesRegex(ContractError, 'stale'):
                open_current(output, current_review_revision=review['revision'])
            old_generation, old_index = open_current(
                output, current_review_revision=first['review_revision'])
            with self.assertRaisesRegex(ContractError, 'stale'):
                search_export(old_generation, old_index,
                              selection(vocabulary['configurations'][0]), 'pump',
                              current_review_revision=review['revision'])
            self.assertEqual(open_current(
                output, current_review_revision=first['review_revision'])[0],
                first['generation'])
            second = publish_library(output, sources, vocabulary, review)
            self.assertNotEqual(first['library_revision'], second['library_revision'])
            self.assertEqual(open_current(
                output, current_review_revision=review['revision'])[0],
                second['generation'])

    def test_bounded_cache_uses_review_revision_and_evicts(self):
        vocab = make_vocabulary()
        library = {'revision': 'a' * 64}
        review = {'revision': 'b' * 64}
        cache = ScopeCache(max_entries=1)
        calls = []

        def resolve():
            calls.append(1)
            return len(calls)

        first = cache.get(library, vocab, review, {'make_id': vocab['makes'][0]['id']},
                          resolver=resolve)
        self.assertEqual(first, 1)
        self.assertEqual(cache.get(library, vocab, review,
                                   {'make_id': vocab['makes'][0]['id']},
                                   resolver=resolve), 1)
        review['revision'] = 'c' * 64
        self.assertEqual(cache.get(library, vocab, review,
                                   {'make_id': vocab['makes'][0]['id']},
                                   resolver=resolve), 2)
        self.assertEqual(len(cache._entries), 1)

    def test_static_memberships_equal_python_for_partial_and_qualifier_states(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = make_vocabulary()
            ford = vocabulary['configurations'][0]
            ford['qualifiers'] = {'transmission': 'automatic'}
            ford['id'] = configuration_id(ford['make_id'], ford['model_id'],
                                          ford['model_year'], ford['engine_id'],
                                          ford['qualifiers'])
            vocabulary['revision'] = digest({key: value for key, value in
                                             vocabulary.items() if key != 'revision'})
            packages, evidence_sets = self._sources(root, vocabulary)
            evidence = evidence_sets[0]
            assertion = next(item for item in evidence['assertions']
                             if item['derivation'] == 'explicit_structured')
            assertion['alternatives'][0]['qualifiers'] = {
                'transmission': {'state': 'exact', 'value': 'automatic'}}
            assertion['digest'] = assertion_digest(assertion)
            assertion['id'] = sidecar_id('ev', evidence['source_id'],
                                       assertion['subject_id'], assertion['digest'])
            evidence['revision'] = evidence_revision(evidence)
            review = new_overlay(evidence, vocabulary)
            output = os.path.join(root, 'library')
            publish_library(output, [{'package': packages[0], 'evidence': evidence}],
                            vocabulary, review)
            generation, index = open_current(
                output, current_review_revision=review['revision'])
            with open(os.path.join(generation, 'library.json'), encoding='utf-8') as stream:
                library = json.load(stream)
            relative = library['packages'][0]['root']
            copied = verified_package(os.path.join(generation, relative),
                                      evidence, vocabulary)
            copied['relative_root'] = relative
            for fingerprint, exported in index['scopes'].items():
                scope = exported['scope']
                resolved = resolve_scope(
                    library, [copied], vocabulary, review, scope['selection'],
                    mode=scope['mode'], include_reference=scope['include_reference'],
                    browse_all=scope['browse_all'])
                self.assertEqual(resolved['scope'], scope)
                self.assertEqual(resolved['scope']['fingerprint'], fingerprint)
            full = selection(ford)
            missing = search_export(generation, index, full, 'pump',
                                    mode='include_possible',
                                    current_review_revision=review['revision'])
            self.assertTrue(missing['results'])
            confirmed_without = search_export(
                generation, index, full, 'pump',
                current_review_revision=review['revision'])['results']
            known = search_export(generation, index,
                                  {**full, 'qualifiers': {'transmission': 'automatic'}},
                                  'pump', current_review_revision=review['revision'])
            self.assertGreater(len(known['results']), len(confirmed_without))
            self.assertGreater(len(missing['results']), len(confirmed_without))


if __name__ == '__main__':
    unittest.main()
