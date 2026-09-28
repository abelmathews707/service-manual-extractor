"""A9 offline viewer export gates for the reviewed multi-manual library."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_library_export
from test_applicability_contracts import make_vocabulary
from test_sources import pdf_bytes

from sme.contract import ContractError
from sme.evidence import capture_evidence
from sme.library_export import open_current, publish_library, search_export
from sme.library_viewer import build_library_viewer
from sme.normalize import normalize_source
from sme.review import decide, new_overlay, propose
from sme.source import extract_source


class LibraryViewerTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('pdfinfo') and shutil.which('pdftotext'),
                         'native PDF reader test requires Poppler (covered in pdf-and-schema CI)')
    def test_mixed_original_retained_in_navigation_but_absent_from_every_shard(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = make_vocabulary()
            original = Path(root, 'mixed.pdf')
            original.write_bytes(pdf_bytes(('2006 Chevrolet Silverado 1500 '
                                            '4.3L and 6.0L engine sections',)))
            extracted = os.path.join(root, 'extracted')
            package = os.path.join(root, 'package')
            extract_source(str(original), extracted)
            normalize_source(extracted, package)
            evidence = capture_evidence(package, vocabulary)
            unit = evidence['units'][0]
            self.assertTrue(unit['mixed_content'])
            self.assertEqual(unit['search']['state'], 'metadata_only')
            review = new_overlay(evidence, vocabulary)
            overlay = Path(root, 'review.json')
            overlay.write_text(json.dumps(review), encoding='utf-8')
            library = os.path.join(root, 'library')
            publish_library(library, [{'package': package, 'evidence': evidence}],
                            vocabulary, review)
            site = os.path.join(root, 'site')
            result = build_library_viewer(library, overlay, site)
            self.assertEqual(result['units'], 0)
            self.assertEqual(result['unsearchable_originals'], 1)
            details = json.loads(Path(site, 'data', 'unit-details.json').read_text())
            self.assertTrue(details[unit['id']]['metadata_only'])
            self.assertTrue(details[unit['id']]['source_url'].endswith('#page=1'))
            manifest = json.loads(Path(site, 'data', 'manifest.json').read_text())
            self.assertEqual(manifest['books'][0]['navigation'][0]['document_id'], unit['id'])
            index = json.loads(Path(site, 'data', 'library-index.json').read_text())
            self.assertFalse(index['shards'])
            self.assertFalse(any(entry['scope']['eligible'] for entry in index['scopes'].values()))
            self.assertIn('4.3L and 6.0L', Path(site, 'content', 'manual-unit',
                                              unit['id'] + '.html').read_text())

    def test_builds_scope_bound_site_without_changing_legacy_viewer(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = make_vocabulary()
            packages, evidence = test_library_export.LibraryExportTests()._sources(
                root, vocabulary)
            review = new_overlay(evidence, vocabulary)
            overlay = Path(root, 'current-review.json')
            overlay.write_text(json.dumps(review), encoding='utf-8')
            library_root = os.path.join(root, 'library')
            published = publish_library(library_root, [
                {'package': package, 'evidence': item}
                for package, item in zip(packages, evidence)], vocabulary, review)
            destination = os.path.join(root, 'site')
            result = build_library_viewer(library_root, overlay, destination)
            self.assertEqual(result['review_revision'], review['revision'])
            cli = subprocess.run(
                [sys.executable, '-m', 'sme', 'build-library-viewer', library_root,
                 '--review-overlay', str(overlay), '-o', os.path.join(root, 'cli-site'),
                 '--json'], check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(cli.stdout)['units'], result['units'])
            manifest = json.loads(Path(destination, 'data', 'manifest.json').read_text())
            self.assertEqual(manifest['viewerMode'], 'library')
            self.assertGreaterEqual(len(manifest['books']), 4)
            def leaves(nodes):
                return sum(bool(node['document_id']) + leaves(node['children'])
                           for node in nodes)
            self.assertTrue(all(leaves(book['navigation']) == book['units']
                                for book in manifest['books']))
            self.assertEqual(manifest['libraryRevision'], published['library_revision'])
            index = json.loads(Path(destination, 'data', 'library-index.json').read_text())
            source_generation, source_index = open_current(
                library_root, current_review_revision=review['revision'])
            self.assertEqual(index['scopes'], source_index['scopes'])
            for shard in index['shards'].values():
                self.assertTrue(Path(destination, 'data', shard['path']).is_file())
            units = json.loads(Path(destination, 'data', 'unit-details.json').read_text())
            searchable = {unit for entry in index['scopes'].values()
                          for unit in entry['unit_occurrences']}
            self.assertEqual({unit for unit, detail in units.items()
                              if not detail['metadata_only']}, searchable)
            self.assertFalse({unit for unit, detail in units.items()
                              if detail['metadata_only']} & searchable)
            ford = vocabulary['configurations'][0]
            selected = {key: ford[key] for key in
                        ('make_id', 'model_id', 'model_year', 'engine_id')}
            found = search_export(source_generation, source_index, selected, 'pump',
                                  current_review_revision=review['revision'])
            self.assertTrue(found['results'])
            entry = index['scopes'][found['fingerprint']]
            self.assertEqual({item['unit_id'] for item in entry['scope']['eligible']},
                             {item['unit_id'] for item in source_index['scopes'][
                                 found['fingerprint']]['scope']['eligible']})
            self.assertTrue(all(Path(destination, 'content', 'manual-unit',
                                     unit + '.html').is_file() for unit in units))
            if evidence[2]['units']:
                pdf_fragment = Path(destination, 'content', 'manual-unit',
                                    evidence[2]['units'][0]['id'] + '.html').read_text()
                self.assertIn('GM-only article', pdf_fragment)
                self.assertTrue(Path(destination, 'content', 'sources').is_dir())
            self.assertTrue(Path(destination, 'content', 'assets').is_dir())

    def test_stale_review_and_changed_shard_refuse_build(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = make_vocabulary()
            packages, evidence = test_library_export.LibraryExportTests()._sources(
                root, vocabulary)
            review = new_overlay(evidence, vocabulary)
            overlay = Path(root, 'current-review.json')
            overlay.write_text(json.dumps(review), encoding='utf-8')
            library_root = os.path.join(root, 'library')
            publish_library(library_root, [{'package': package, 'evidence': item}
                                           for package, item in zip(packages, evidence)],
                            vocabulary, review)
            generation, index = open_current(library_root,
                                             current_review_revision=review['revision'])
            with self.assertRaisesRegex(ContractError, 'outside the immutable'):
                build_library_viewer(library_root, Path(generation, 'review.json'),
                                     os.path.join(root, 'embedded'))
            altered = dict(review, revision='f' * 64)
            overlay.write_text(json.dumps(altered), encoding='utf-8')
            with self.assertRaisesRegex(ContractError, 'revision does not match'):
                build_library_viewer(library_root, overlay, os.path.join(root, 'stale'))
            overlay.write_text(json.dumps(review), encoding='utf-8')
            shard = next(iter(index['shards'].values()))
            path = Path(generation, shard['path'])
            path.write_text(path.read_text() + ' ', encoding='utf-8')
            # A whitespace-only change does not affect the parsed value, but
            # publication is still refused if the parsed shard membership changes.
            payload = json.loads(path.read_text())
            payload[0]['text'] = 'changed text'
            path.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(ContractError, 'search shard changed'):
                build_library_viewer(library_root, overlay, os.path.join(root, 'changed'))

    @unittest.skipUnless(shutil.which('pdfinfo') and shutil.which('pdftotext'),
                         'native PDF review test requires Poppler (covered in pdf-and-schema CI)')
    def test_rebuilt_snapshot_changes_only_reviewed_membership(self):
        with tempfile.TemporaryDirectory() as root:
            vocabulary = make_vocabulary()
            packages, evidence = test_library_export.LibraryExportTests()._sources(
                root, vocabulary)
            sources = [{'package': package, 'evidence': item}
                       for package, item in zip(packages, evidence)]
            overlay = Path(root, 'current-review.json')
            review = new_overlay(evidence, vocabulary)
            overlay.write_text(json.dumps(review), encoding='utf-8')
            library_root = os.path.join(root, 'library')
            first = publish_library(library_root, sources, vocabulary, review)
            initial = build_library_viewer(library_root, overlay,
                                           os.path.join(root, 'first-site'))
            self.assertEqual(initial['review_revision'], first['review_revision'])
            ford = vocabulary['configurations'][0]
            selected = {key: ford[key] for key in
                        ('make_id', 'model_id', 'model_year', 'engine_id')}
            generation, index = open_current(library_root,
                                             current_review_revision=review['revision'])
            before = search_export(generation, index, selected, 'GM-only',
                                   current_review_revision=review['revision'])
            self.assertEqual(before['results'], [])
            gm_pdf = evidence[2]
            review = propose(review, evidence, vocabulary,
                             source_id=gm_pdf['source_id'],
                             subject_id=gm_pdf['units'][0]['id'],
                             relation='section_applies',
                             target_configuration_ids=[ford['id']],
                             evidence_ids=[gm_pdf['assertions'][0]['id']],
                             reviewer='test', timestamp='2026-09-27T10:00:00Z',
                             reason='Reviewed shared section')
            review = decide(review, evidence, vocabulary,
                            prior_event_id=review['events'][0]['id'],
                            action='accept', reviewer='test',
                            timestamp='2026-09-27T10:01:00Z',
                            reason='Confirmed source supports this target')
            overlay.write_text(json.dumps(review), encoding='utf-8')
            with self.assertRaisesRegex(ContractError, 'stale'):
                build_library_viewer(library_root, overlay,
                                     os.path.join(root, 'stale-site'))
            second = publish_library(library_root, sources, vocabulary, review)
            self.assertNotEqual(first['review_revision'], second['review_revision'])
            built = build_library_viewer(library_root, overlay,
                                         os.path.join(root, 'second-site'))
            self.assertEqual(built['review_revision'], second['review_revision'])
            generation, index = open_current(library_root,
                                             current_review_revision=review['revision'])
            after = search_export(generation, index, selected, 'GM-only',
                                  current_review_revision=review['revision'])
            self.assertEqual([item['unit_id'] for item in after['results']],
                             [gm_pdf['units'][0]['id']])


if __name__ == '__main__':
    unittest.main()
