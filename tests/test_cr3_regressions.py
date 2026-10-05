"""Authored regressions for the confirmed CR1 extractor findings."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from test_applicability_contracts import make_vocabulary
from test_ford_adapter import _epl, _files
from test_formats import make_arc, payload
from test_sources import html_files, pdf_bytes

from fsd.build import build, clean_fragment
from sme import cli
from sme.applicability_contracts import configuration_id, digest
from sme.discovery import discover_folder
from sme.evidence import capture_evidence
from sme.ford_adapter import import_ford
from sme.library import verified_package
from sme.matching import match_unit
from sme.normalize import normalize_source
from sme.orchestrate import process_folder
from sme.source import Member, SourceError, _content_digest, extract_source
from sme.vehicle_interpretation import interpret_statement


def write_files(root, files):
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class CR3ExtractorTests(unittest.TestCase):
    def test_original_and_inventory_changes_reject_html_pdf_and_ford(self):
        for kind in ('html', 'pdf', 'ford'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                package = root / 'package'
                if kind == 'ford':
                    write_files(root / 'disc', {'content/useni4/SAA.arc': make_arc(dict(_files()))})
                    import_ford(root / 'disc', package, ['content/useni4/saa.arc'])
                else:
                    source = root / ('manual.pdf' if kind == 'pdf' else 'html')
                    if kind == 'pdf':
                        source.write_bytes(pdf_bytes(('Check voltage.',)))
                    else:
                        write_files(source, html_files())
                    extract_source(source, root / 'raw')
                    normalize_source(root / 'raw', package)
                verified_package(package)
                inventory_path = package / '.sme-source-inventory.json'
                inventory = json.loads(inventory_path.read_text())
                member = inventory['members'][0]
                original = package / member['path']
                original.write_bytes(original.read_bytes() + b' changed')
                import hashlib
                member['sha256'] = hashlib.sha256(original.read_bytes()).hexdigest()
                member['size'] = original.stat().st_size
                inventory['selected_content_sha256'] = _content_digest(
                    [Member(**item) for item in inventory['members']],
                    inventory['empty_directories'])
                inventory['source_content_sha256'] = inventory['selected_content_sha256']
                inventory_path.write_text(json.dumps(inventory))
                with self.assertRaisesRegex(SourceError, 'inventory is unbound or changed'):
                    verified_package(package)
                with self.assertRaisesRegex(SourceError, 'inventory is unbound or changed'):
                    capture_evidence(package, make_vocabulary())

    def test_vin_restriction_survives_extract_evidence_and_match(self):
        vocabulary = make_vocabulary()
        config = vocabulary['configurations'][0]
        variants = []
        for vin in ('W', 'X'):
            variant = copy.deepcopy(config)
            variant['qualifiers'] = {'vin': vin}
            variant['id'] = configuration_id(variant['make_id'], variant['model_id'],
                variant['model_year'], variant['engine_id'], variant['qualifiers'])
            variants.append(variant)
        vocabulary['configurations'][:1] = variants
        vocabulary['revision'] = digest({k: v for k, v in vocabulary.items() if k != 'revision'})
        statement = '2003 Ford F-250 6.0L diesel VIN W only'
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = html_files()
            files['pages/1.html'] = ('<h1>Procedure</h1>'
                                    '<p>2003 Ford F-250 6.0L diesel</p><p>' + statement +
                                    '</p><p>Check voltage.</p>').encode()
            write_files(root / 'source', files)
            extract_source(root / 'source', root / 'raw')
            normalize_source(root / 'raw', root / 'package')
            package = verified_package(root / 'package')
            evidence = capture_evidence(root / 'package', vocabulary)
            unit = next(u for u in evidence['units'] if u['citation']['path'] == 'pages/1.html')
            for variant in variants:
                selection = {key: variant[key] for key in
                             ('make_id', 'model_id', 'model_year', 'engine_id', 'qualifiers')}
                result = match_unit(evidence, package['manifest'], vocabulary,
                                    unit['id'], selection)
                self.assertEqual(result['search_eligible'], variant['qualifiers']['vin'] == 'W')
            for wording in ('except VIN W', 'VIN W or X', 'VIN W/X', 'VIN W, X',
                            'VIN Q', 'RPO unknown'):
                _, resolved = interpret_statement('2003 Ford F-250 6.0L diesel ' + wording,
                                                  vocabulary)
                self.assertFalse(resolved, wording)

    def test_partial_import_remains_partial_on_cache_and_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = html_files()
            files['pages/bad.html'] = b'<meta charset="unsupported-encoding"><p>Unreadable</p>'
            write_files(root / 'incoming' / 'manual', files)
            for cached in (False, True):
                result = process_folder(root / 'incoming', root / 'cache')
                row = result['results'][0]
                self.assertEqual(row['status'], 'partial')
                self.assertFalse(result['ok'])
                self.assertEqual(row['packages'][0]['cached'], cached)
                self.assertTrue(row['packages'][0]['failures'])
                with self.assertRaisesRegex(SourceError, 'inspection only'):
                    verified_package(row['packages'][0]['path'])
            for options in ([], ['--json']):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(['process-folder', str(root / 'incoming'),
                        '--out', str(root / 'cache'), *options]), 1)

    def test_generic_pod_cannot_be_discovered_as_ford(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_files(root, {'generic/content/books/NONFORD.arc':
                              make_arc({'README.TXT': payload(stored=[b'Other publisher'])})})
            source = discover_folder(root)['sources'][0]
            self.assertNotEqual(source['status'], 'recognized')
            self.assertIsNone(source['route'])
            write_files(root, {'generic/content/books/SAA.arc': make_arc(dict(_files()))})
            source = discover_folder(root)['sources'][0]
            self.assertEqual(source['status'], 'recognized')
            self.assertEqual(len(source['archives']), 1)
            self.assertEqual(len(source['unsupported_archives']), 1)

    def test_legacy_build_preserves_local_content_and_blocks_active_markup(self):
        fragment = clean_fragment('<p onclick="bad()">Check voltage.</p>'
            '<img src="https://example.invalid/probe" onerror="bad()">'
            '<a href="javascript:bad()">bad</a><iframe src="//example.invalid"></iframe>'
            '<img src="LOCAL.PNG"><a href="NEXT.HTM">Next</a>', 'wsm')
        self.assertNotIn('onerror', fragment)
        self.assertNotIn('onclick', fragment)
        self.assertNotIn('example.invalid', fragment)
        self.assertNotIn('javascript:', fragment)
        self.assertIn('content/wsm/local.png', fragment)
        self.assertIn('#/wsm/next', fragment)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_files(root / 'extracted', {'SAA/SAA.EPL': _epl(),
                'SAA/PAGE.HTM': b'<h1>Authored test</h1><p>Check voltage.</p>',
                'SAA/BAD.SVG': b'<svg xmlns="http://www.w3.org/2000/svg" onclick="bad()"/>',
                'SAA/GOOD.SVG': (b'<svg xmlns="http://www.w3.org/2000/svg">'
                                 b'<path d="M0 0h10"/></svg>')})
            build(root / 'extracted', root / 'site', log=lambda _: None)
            self.assertIn('Check voltage.', (root / 'site/content/wsm/page.html').read_text())
            self.assertIn('Diagram unavailable', (root / 'site/content/wsm/bad.svg').read_text())
            self.assertIn('path', (root / 'site/content/wsm/good.svg').read_text())
